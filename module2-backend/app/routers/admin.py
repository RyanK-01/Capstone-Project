import html

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, ValidationError, field_serializer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Any, Literal

from app.database import get_db
from app.models import AuditAction, Courses, Sessions, SessionStatus, Users
from app.retention import set_user_active
from app.routers.enrollments import enroll_student, resp_enrollment
from app.routers.security import get_password_hash, require_role
from app.utils import write_audit

# -----------------------------------------------------------------------------
# Admin Endpoints (admin.py) - Required for automated testing
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/admin", tags=["admin"])

# Models
class resp_user_state(BaseModel):
    id: str
    email: str
    is_active: bool
    message: str

class bulk_user(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: Literal["student", "instructor", "ta", "admin"] = "student"

class bulk_users_request(BaseModel):
    users: list[Any] = Field(min_length=1, max_length=1000)

class resp_bulk_user(BaseModel):
    id: str
    email: str
    full_name: str
    role: str

    # XSS Prevention
    @field_serializer("full_name")
    def escape_name(self, value: str) -> str:
        return html.escape(value)

class resp_bulk_users(BaseModel):
    created: int
    failed: int
    users: list[resp_bulk_user]
    errors: list[dict]

class session_status_request(BaseModel):
    status: Literal["scheduled", "active", "closed", "cancelled"]

class resp_session_status(BaseModel):
    id: str
    name: str
    status: str
    message: str

    # XSS Prevention
    @field_serializer("name")
    def escape_name(self, value: str) -> str:
        return html.escape(value)

class admin_enrollment(BaseModel):
    student_id: str = Field(min_length=1, max_length=36)
    course_id: str = Field(min_length=1, max_length=36)

def get_user_or_404(user_id: str, db: Session) -> Users:
    user = db.query(Users).filter(Users.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return user

def set_active(user_id: str, active: bool, request: Request, admin: Users, db: Session) -> resp_user_state:
    user = get_user_or_404(user_id, db)
    if not active and user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot demote or deactivate themselves")

    set_user_active(user, active)  # Also starts or stops the 30-day retention clock
    write_audit(db, request, admin.id, AuditAction.USER_UPDATED, "user", user.id, {"is_active": active})
    db.commit()

    return resp_user_state(id=user.id, email=user.email, is_active=user.is_active,
                           message=f"User {'activated' if active else 'deactivated'} successfully")

# PATCH /admin/users/{user_id}/deactivate - Deactivate user (admin only)
@routers.patch("/users/{user_id}/deactivate", response_model=resp_user_state, status_code=status.HTTP_200_OK)
def deactivate_user(user_id: str, request: Request, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return set_active(user_id, False, request, admin, db)

# PATCH /admin/users/{user_id}/activate - Activate user (admin only)
@routers.patch("/users/{user_id}/activate", response_model=resp_user_state, status_code=status.HTTP_200_OK)
def activate_user(user_id: str, request: Request, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return set_active(user_id, True, request, admin, db)

# POST /admin/users/bulk - Bulk create users (admin only)
@routers.post("/users/bulk", response_model=resp_bulk_users, status_code=status.HTTP_201_CREATED)
def bulk_create_users(body: bulk_users_request, request: Request, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    created: list[Users] = []
    errors: list[dict] = []
    seen: set[str] = set()

    for index, raw in enumerate(body.users):
        # Each entry is validated on its own so one bad row does not fail the whole batch
        try:
            item = bulk_user.model_validate(raw)
        except ValidationError:
            errors.append({"index": index, "email": raw.get("email") if isinstance(raw, dict) else None, "error": "Invalid user data"})
            continue

        email = str(item.email)
        if email.lower() in seen or db.query(Users.id).filter(Users.email == email).first() is not None:
            errors.append({"index": index, "email": email, "error": "Email already registered"})
            continue
        seen.add(email.lower())

        user = Users(email=email, full_name=item.full_name, hashed_password=get_password_hash(item.password), role=item.role)
        try:
            # A savepoint keeps the users created so far if this one fails
            with db.begin_nested():
                db.add(user)
                db.flush()
        except IntegrityError:
            errors.append({"index": index, "email": email, "error": "Email already registered"})
            continue

        write_audit(db, request, admin.id, AuditAction.USER_CREATED, "user", user.id, {"role": item.role, "source": "admin_bulk"})
        created.append(user)

    db.commit()

    return resp_bulk_users(
        created=len(created),
        failed=len(errors),
        users=[resp_bulk_user(id=u.id, email=u.email, full_name=u.full_name, role=str(getattr(u.role, "value", u.role))) for u in created],
        errors=errors,
    )

# PATCH /admin/sessions/{session_id}/status - Update session status (admin only)
@routers.patch("/sessions/{session_id}/status", response_model=resp_session_status, status_code=status.HTTP_200_OK)
def set_session_status(session_id: str, body: session_status_request, request: Request, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    session = db.query(Sessions).filter(Sessions.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    old = session.status.value if isinstance(session.status, SessionStatus) else str(session.status)
    new = SessionStatus(body.status)

    # Any transition is allowed here so tests can set up edge cases
    now = datetime.now(timezone.utc)
    if new == SessionStatus.ACTIVE and session.actual_start is None:
        session.actual_start = now
    if new == SessionStatus.CLOSED and session.actual_start is not None and session.actual_end is None:
        session.actual_end = now
    session.status = new

    write_audit(db, request, admin.id, AuditAction.SESSION_UPDATED, "session", session.id, {"status": body.status, "previous_status": old})
    db.commit()

    return resp_session_status(id=session.id, name=session.name, status=body.status,
                               message=f"Session status changed from '{old}' to '{body.status}'")

# POST /admin/enrollments/ - Admin enrollment creation (admin only)
@routers.post("/enrollments/", response_model=resp_enrollment, status_code=status.HTTP_201_CREATED)
def admin_enroll(body: admin_enrollment, request: Request, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    course = db.query(Courses).filter(Courses.id == body.course_id, Courses.is_active.is_(True)).first()
    student = db.query(Users).filter(Users.id == body.student_id, Users.role == "student").first()
    if course is None or student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    enrollment, newly_enrolled = enroll_student(db, request, admin, student, course)
    if not newly_enrolled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student already enrolled")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student already enrolled")
    db.refresh(enrollment)

    return enrollment
