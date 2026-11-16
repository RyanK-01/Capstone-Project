import html

import httpx

from datetime import datetime
from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.models import AuditAction, Users, Enrollments
from app.retention import set_user_active
from app.risk import FACE_SERVICE_URL
from app.routers.security import get_current_user, require_role
from app.utils import taught_by, write_audit

# -----------------------------------------------------------------------------
# User Management Endpoints (users.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/users", tags=["users"])

# Models
class resp_profile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str
    camera_consent: bool = False
    geolocation_consent: bool = False
    face_enrolled: bool = False
    created_at: datetime
    
    # XSS Prevention
    @field_serializer("full_name")
    def escape_full_name(self, value: str) -> str:
        return html.escape(value)
    
class update_profile(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    camera_consent: bool | None = None
    geolocation_consent: bool | None = None

class face_enroll_request(BaseModel):
    image: str = Field(min_length=1)

class resp_face_enroll(BaseModel):
    success: bool
    message: str
    face_enrolled: bool
    quality_score: float | None = None

class resp_user(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool = False
    face_enrolled: bool = False
    created_at: datetime
    
    # XSS Prevention
    @field_serializer("full_name")
    def escape_full_name(self, value: str) -> str:
        return html.escape(value)
  
class resp_user_list(BaseModel):
    items: list[resp_user]
    total: int
    limit: int
    offset: int

class admin_update_user(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["student", "instructor", "ta", "admin"] | None = None
    is_active: bool | None = None
   

# GET /users/me - Current user info
@routers.get("/me", response_model=resp_profile, status_code=status.HTTP_200_OK)
def get_me(user: Users = Depends(get_current_user)):
    return user

# PUT /users/me - Update profile / consent flags
@routers.put("/me", response_model=resp_profile, status_code=status.HTTP_200_OK)
def update_me(body: update_profile, request: Request, user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)

    if "full_name" in data:
        user.full_name = data["full_name"]
    if "camera_consent" in data:
        user.camera_consent = data["camera_consent"]
    if "geolocation_consent" in data:
        user.geolocation_consent = data["geolocation_consent"]
    
    if data:
        write_audit(db, request, user.id, AuditAction.USER_UPDATED, "user", user.id, {"fields": sorted(data)})

    db.commit()
    db.refresh(user)

    return user

# POST /users/me/face/enroll - Enroll face (proxies to the face service)
@routers.post("/me/face/enroll", response_model=resp_face_enroll, status_code=status.HTTP_200_OK)
def enroll_face(body: face_enroll_request, request: Request, user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.camera_consent:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Camera consent is required before enrolling a face")

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(f"{FACE_SERVICE_URL}/face/enroll", json={"user_id": user.id, "image": body.image, "camera_consent": True})
    except httpx.HTTPError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Face recognition service unavailable")

    if response.status_code == 400:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No face detected in the provided image")
    if response.status_code not in (200, 201):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Face recognition service unavailable")

    result = response.json()
    if not result.get("enrollment_successful"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No face detected in the provided image")

    user.face_embedding_hash = result.get("face_template_hash")
    user.face_enrolled = True

    write_audit(db, request, user.id, AuditAction.FACE_ENROLLED, "user", user.id, {"quality_score": result.get("quality_score")})

    db.commit()

    return resp_face_enroll(success=True, message="Face enrolled successfully", face_enrolled=True, quality_score=result.get("quality_score"))


# GET /users/ - List users (admin only)
@routers.get("/", response_model=resp_user_list, status_code=status.HTTP_200_OK)
def user_lists(role: Literal["student", "instructor", "ta", "admin"] | None = Query(default=None), is_active: bool | None = Query(default=None), search: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0), admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db),):
    query = db.query(Users)
    
    if role is not None:
        query = query.filter(Users.role == role)
    if is_active is not None:
        query = query.filter(Users.is_active.is_(is_active))
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Users.full_name.ilike(pattern), Users.email.ilike(pattern)))

    total = query.count()
    items = query.order_by(Users.created_at.desc()).offset(offset).limit(limit).all()
    
    return resp_user_list(items=items, total=total, limit=limit, offset=offset)

# GET /users/{user_id} - User details (admin only)
@routers.get("/{user_id}", response_model=resp_user, status_code=status.HTTP_200_OK)
def read_user(user_id: str, current: Users = Depends(require_role("admin", "instructor")), db: Session = Depends(get_db)):
    target = db.query(Users).filter(Users.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    
    if not can_view_user(current, target, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    return target

def can_view_user(current: Users, target: Users, db: Session) -> bool:
    if current.role == "admin":
        return True

    # Instructors may view students enrolled in a course they run (see taught_by)
    teaches = (
        db.query(Enrollments.id)
        .filter(
            Enrollments.student_id == target.id,
            Enrollments.is_active.is_(True),
            taught_by(current, Enrollments.course_id),
        )
        .first()
    )
    return teaches is not None

# PATCH /users/{user_id} - Update user (admin only)
@routers.patch("/{user_id}", response_model=resp_user, status_code=status.HTTP_200_OK)
def patch_user(user_id: str, body: admin_update_user, request: Request, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    target = db.query(Users).filter(Users.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    
    data = body.model_dump(exclude_unset=True)
    
    # Prevent admin from locking themselve
    if target.id == admin.id and (data.get("is_active") is False or ("role" in data and data["role"] != "admin")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot demote or deactivate themselves")
    
    if "role" in data and data["role"] is not None:
        target.role = data["role"]
    if "is_active" in data and data["is_active"] is not None:
        set_user_active(target, data["is_active"])  # Also starts or stops the 30-day retention clock

    if data:
        write_audit(db, request, admin.id, AuditAction.USER_UPDATED, "user", target.id, data)

    db.commit()
    db.refresh(target)
    
    return target