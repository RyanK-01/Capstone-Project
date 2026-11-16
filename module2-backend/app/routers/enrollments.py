import html
import secrets

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditAction, Courses, Enrollments, Users
from app.routers.security import get_password_hash, require_role
from app.utils import require_course_access, write_audit

# -----------------------------------------------------------------------------
# Enrollment Endpoints (enrollments.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/enrollments", tags=["enrollments"])

# Models
class resp_my_enrollment(BaseModel):
    id: str
    course_id: str
    course_code: str
    course_name: str
    semester: str
    enrolled_at: datetime
    is_active: bool

    # XSS Prevention
    @field_serializer("course_code", "course_name", "semester")
    def escape_text(self, value: str) -> str:
        return html.escape(value)

class resp_course_student(BaseModel):
    id: str
    student_id: str
    student_email: str
    student_name: str
    enrolled_at: datetime
    is_active: bool
    face_enrolled: bool = False

    # XSS Prevention
    @field_serializer("student_name")
    def escape_name(self, value: str) -> str:
        return html.escape(value)

class resp_course_students(BaseModel):
    course_id: str
    course_code: str
    total_enrolled: int
    students: list[resp_course_student]

    # XSS Prevention
    @field_serializer("course_code")
    def escape_code(self, value: str) -> str:
        return html.escape(value)

class create_enrollment(BaseModel):
    student_id: str = Field(min_length=1, max_length=36)
    course_id: str = Field(min_length=1, max_length=36)

class resp_enrollment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    student_id: str
    course_id: str
    enrolled_at: datetime
    is_active: bool
    dropped_at: datetime | None = None

class bulk_enrollment(BaseModel):
    course_id: str = Field(min_length=1, max_length=36)
    student_emails: list[EmailStr] = Field(min_length=1, max_length=500)
    create_accounts: bool = False

class bulk_detail(BaseModel):
    email: str
    status: str

    # XSS Prevention
    @field_serializer("email")
    def escape_email(self, value: str) -> str:
        return html.escape(value)

class resp_bulk_enrollment(BaseModel):
    enrolled: int
    already_enrolled: int
    not_found: int
    created: int
    details: list[bulk_detail]

def get_course_or_404(course_id: str, db: Session) -> Courses:
    course = db.query(Courses).filter(Courses.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return course

def enroll_student(db: Session, request: Request, actor: Users, student: Users, course: Courses) -> tuple[Enrollments, bool]:
    enrollment = db.query(Enrollments).filter(Enrollments.student_id == student.id, Enrollments.course_id == course.id).first()

    if enrollment is not None and enrollment.is_active:
        return enrollment, False

    if enrollment is not None:
        enrollment.is_active = True
        enrollment.enrolled_at = datetime.now(timezone.utc)
        enrollment.dropped_at = None
    else:
        enrollment = Enrollments(student_id=student.id, course_id=course.id)
        db.add(enrollment)
    db.flush()

    write_audit(db, request, actor.id, AuditAction.ENROLLMENT_ADDED, "enrollment", enrollment.id,
                {"student_id": student.id, "course_id": course.id})
    return enrollment, True

# GET /enrollments/my-enrollments - Student's enrollments
@routers.get("/my-enrollments", response_model=list[resp_my_enrollment], status_code=status.HTTP_200_OK)
def my_enrollments(student: Users = Depends(require_role("student")), db: Session = Depends(get_db)):
    rows = (
        db.query(Enrollments, Courses)
        .join(Courses, Courses.id == Enrollments.course_id)
        .filter(Enrollments.student_id == student.id)
        .order_by(Enrollments.enrolled_at.desc())
        .all()
    )

    return [
        resp_my_enrollment(
            id=enrollment.id,
            course_id=course.id,
            course_code=course.code,
            course_name=course.name,
            semester=course.semester,
            enrolled_at=enrollment.enrolled_at,
            is_active=enrollment.is_active,
        )
        for enrollment, course in rows
    ]

# GET /enrollments/course/{course_id} - Students enrolled in a course
@routers.get("/course/{course_id}", response_model=resp_course_students, status_code=status.HTTP_200_OK)
def course_enrollments(
    course_id: str,
    is_active: bool = Query(default=True),
    search: str | None = Query(default=None, max_length=255),
    user: Users = Depends(require_role("admin", "instructor", "ta")),
    db: Session = Depends(get_db),
):
    course = get_course_or_404(course_id, db)
    require_course_access(user, course.id, db)

    query = (
        db.query(Enrollments, Users)
        .join(Users, Users.id == Enrollments.student_id)
        .filter(Enrollments.course_id == course.id, Enrollments.is_active.is_(is_active))
    )
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Users.full_name.ilike(pattern), Users.email.ilike(pattern)))

    rows = query.order_by(Users.full_name).all()
    total_enrolled = db.query(Enrollments).filter(Enrollments.course_id == course.id, Enrollments.is_active.is_(True)).count()

    return resp_course_students(
        course_id=course.id,
        course_code=course.code,
        total_enrolled=total_enrolled,
        students=[
            resp_course_student(
                id=enrollment.id,
                student_id=student.id,
                student_email=student.email,
                student_name=student.full_name,
                enrolled_at=enrollment.enrolled_at,
                is_active=enrollment.is_active,
                face_enrolled=bool(student.face_enrolled),
            )
            for enrollment, student in rows
        ],
    )

# POST /enrollments/ - Enroll a student
@routers.post("/", response_model=resp_enrollment, status_code=status.HTTP_201_CREATED)
def add_enrollment(body: create_enrollment, request: Request, user: Users = Depends(require_role("admin", "instructor")), db: Session = Depends(get_db)):
    course = get_course_or_404(body.course_id, db)
    student = db.query(Users).filter(Users.id == body.student_id, Users.role == "student").first()
    if student is None or not course.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    require_course_access(user, course.id, db)

    enrollment, newly_enrolled = enroll_student(db, request, user, student, course)
    if not newly_enrolled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student already enrolled")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Student already enrolled")
    db.refresh(enrollment)

    return enrollment

# POST /enrollments/bulk - Bulk enroll
@routers.post("/bulk", response_model=resp_bulk_enrollment, status_code=status.HTTP_200_OK)
def bulk_enroll(body: bulk_enrollment, request: Request, user: Users = Depends(require_role("admin", "instructor")), db: Session = Depends(get_db)):
    course = get_course_or_404(body.course_id, db)
    if not course.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    require_course_access(user, course.id, db)

    result = {"enrolled": 0, "already_enrolled": 0, "not_found": 0, "created": 0}
    details: list[bulk_detail] = []

    # Emails are matched case-insensitively and duplicates in the request are ignored.
    emails = list(dict.fromkeys(str(email).lower() for email in body.student_emails))
    for email in emails:
        student = db.query(Users).filter(func.lower(Users.email) == email).first()
        was_created = False

        if student is None and body.create_accounts:
            # No password is shared; the student has to be given access through a reset.
            student = Users(
                email=email,
                full_name=email.split("@")[0],
                hashed_password=get_password_hash(secrets.token_urlsafe(24)),
                role="student",
            )
            db.add(student)
            db.flush()
            write_audit(db, request, user.id, AuditAction.USER_CREATED, "user", student.id, {"email": email, "source": "bulk_enroll"})
            was_created = True

        if student is None or student.role != "student":
            result["not_found"] += 1
            details.append(bulk_detail(email=email, status="not_found"))
            continue

        _, newly_enrolled = enroll_student(db, request, user, student, course)
        if not newly_enrolled:
            result["already_enrolled"] += 1
            details.append(bulk_detail(email=email, status="already_enrolled"))
        elif was_created:
            result["created"] += 1
            result["enrolled"] += 1
            details.append(bulk_detail(email=email, status="created"))
        else:
            result["enrolled"] += 1
            details.append(bulk_detail(email=email, status="enrolled"))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input data")

    return resp_bulk_enrollment(**result, details=details)

# DELETE /enrollments/{enrollment_id} - Drop enrollment
@routers.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def drop_enrollment(enrollment_id: str, request: Request, user: Users = Depends(require_role("admin", "instructor")), db: Session = Depends(get_db)):
    enrollment = db.query(Enrollments).filter(Enrollments.id == enrollment_id).first()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    require_course_access(user, enrollment.course_id, db)

    # Dropped, not deleted, so the attendance history stays intact.
    if enrollment.is_active:
        enrollment.is_active = False
        enrollment.dropped_at = datetime.now(timezone.utc)
        write_audit(db, request, user.id, AuditAction.ENROLLMENT_REMOVED, "enrollment", enrollment.id,
                    {"student_id": enrollment.student_id, "course_id": enrollment.course_id})
        db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
