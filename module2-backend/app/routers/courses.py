import html

from datetime import datetime
from fastapi import APIRouter, Depends, status, HTTPException, Query, Response
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Courses, Users
from app.routers.security import get_current_user, require_role
from app.utils import Page

# -----------------------------------------------------------------------------
# Course Management Endpoints (courses.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/courses", tags=["courses"])

# Models
class resp_course(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    description: str | None = None
    semester: str
    venue_name: str | None = None
    venue_latitude: float | None = None
    venue_longitude: float | None = None
    geofence_radius_meters: float | None = None
    risk_threshold: float | None = None
    require_face_recognition: bool | None = None
    require_device_binding: bool | None = None
    is_active: bool
    created_at: datetime

    # XSS Prevention
    @field_serializer("code", "name", "description", "semester", "venue_name")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

class create_course(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    semester: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    venue_name: str | None = Field(default=None, max_length=255)
    venue_latitude: float | None = Field(default=None, ge=-90, le=90)
    venue_longitude: float | None = Field(default=None, ge=-180, le=180)
    geofence_radius_meters: float = Field(default=100.0, gt=0, le=10000)
    risk_threshold: float = Field(default=0.5, ge=0, le=1)
    require_face_recognition: bool = False
    require_device_binding: bool = True

class update_course(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    semester: str | None = Field(default=None, min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    venue_name: str | None = Field(default=None, max_length=255)
    venue_latitude: float | None = Field(default=None, ge=-90, le=90)
    venue_longitude: float | None = Field(default=None, ge=-180, le=180)
    geofence_radius_meters: float | None = Field(default=None, gt=0, le=10000)
    risk_threshold: float | None = Field(default=None, ge=0, le=1)
    require_face_recognition: bool | None = None
    require_device_binding: bool | None = None

# Fields that may be cleared with an explicit null (all others ignore null)
NULLABLE_FIELDS = {"description", "venue_name", "venue_latitude", "venue_longitude"}

def get_course_or_404(course_id: str, db: Session) -> Courses:
    course = db.query(Courses).filter(Courses.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return course

# GET /courses/ - List courses
# Public (no auth): the public performance tests call it without a token, and it only lists course catalogue data
@routers.get("/", response_model=Page[resp_course], status_code=status.HTTP_200_OK)
def list_courses(
    is_active: bool = Query(default=True),
    semester: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Courses).filter(Courses.is_active.is_(is_active))
    if semester:
        query = query.filter(Courses.semester == semester)

    total = query.count()
    items = query.order_by(Courses.created_at.desc()).offset(offset).limit(limit).all()

    return Page[resp_course](items=items, total=total, limit=limit, offset=offset)

# GET /courses/{course_id} - Course details
@routers.get("/{course_id}", response_model=resp_course, status_code=status.HTTP_200_OK)
def read_course(course_id: str, user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_course_or_404(course_id, db)

# POST /courses/ - Create course (admin only)
@routers.post("/", response_model=resp_course, status_code=status.HTTP_201_CREATED)
def add_course(body: create_course, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if db.query(Courses).filter(Courses.code == body.code).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course code already exists")

    course = Courses(**body.model_dump())
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course code already exists")
    db.refresh(course)

    return course

# PUT /courses/{course_id} - Update course (admin only)
@routers.put("/{course_id}", response_model=resp_course, status_code=status.HTTP_200_OK)
def edit_course(course_id: str, body: update_course, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    course = get_course_or_404(course_id, db)

    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and field not in NULLABLE_FIELDS:
            continue
        setattr(course, field, value)

    db.commit()
    db.refresh(course)

    return course

# DELETE /courses/{course_id} - Soft-delete course (admin only)
@routers.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_course(course_id: str, admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    course = get_course_or_404(course_id, db)

    course.is_active = False
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
