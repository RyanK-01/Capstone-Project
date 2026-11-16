import html

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, status, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_serializer
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.models import AuditAction, CheckIns, CheckInStatus, Courses, Enrollments, SessionStatus, Sessions, Users
from app.routers.security import get_current_user, require_role
from app.utils import Page, as_utc, write_audit

# -----------------------------------------------------------------------------
# Session Management Endpoints (sessions.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/sessions", tags=["sessions"])

SessionType = Literal["lecture", "tutorial", "lab", "exam"]
StatusName = Literal["scheduled", "active", "closed", "cancelled"]

# Models
class resp_session_summary(BaseModel):
    id: str
    course_id: str
    course_code: str
    course_name: str
    instructor_id: str | None = None
    name: str
    session_type: str | None = None
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: datetime
    checkin_closes_at: datetime
    venue_name: str | None = None
    total_enrolled: int = 0
    checked_in_count: int = 0

    # XSS Prevention
    @field_serializer("course_code", "course_name", "name", "venue_name")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

class resp_active_session(BaseModel):
    id: str
    course_id: str
    course_code: str
    name: str
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: datetime
    checkin_closes_at: datetime
    venue_name: str | None = None

    # XSS Prevention
    @field_serializer("course_code", "name", "venue_name")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

class resp_session(BaseModel):
    id: str
    course_id: str
    instructor_id: str | None = None
    name: str
    session_type: str | None = None
    description: str | None = None
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: datetime
    checkin_closes_at: datetime
    venue_latitude: float | None = None
    venue_longitude: float | None = None
    venue_name: str | None = None
    geofence_radius_meters: float | None = None
    require_liveness_check: bool | None = None
    require_face_match: bool | None = None
    risk_threshold: float | None = None
    qr_code_enabled: bool = False
    created_at: datetime

    # XSS Prevention
    @field_serializer("name", "description", "venue_name")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

class create_session(BaseModel):
    course_id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1, max_length=255)
    session_type: SessionType = "lecture"
    description: str | None = Field(default=None, max_length=2000)
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: datetime | None = None
    checkin_closes_at: datetime | None = None
    venue_latitude: float | None = Field(default=None, ge=-90, le=90)
    venue_longitude: float | None = Field(default=None, ge=-180, le=180)
    venue_name: str | None = Field(default=None, max_length=255)
    geofence_radius_meters: float | None = Field(default=None, gt=0, le=10000)
    require_liveness_check: bool = True
    require_face_match: bool = False
    risk_threshold: float | None = Field(default=None, ge=0, le=1)

class update_session(BaseModel):
    status: StatusName | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    session_type: SessionType | None = None
    description: str | None = Field(default=None, max_length=2000)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    checkin_opens_at: datetime | None = None
    checkin_closes_at: datetime | None = None
    venue_latitude: float | None = Field(default=None, ge=-90, le=90)
    venue_longitude: float | None = Field(default=None, ge=-180, le=180)
    venue_name: str | None = Field(default=None, max_length=255)
    geofence_radius_meters: float | None = Field(default=None, gt=0, le=10000)
    require_liveness_check: bool | None = None
    require_face_match: bool | None = None
    risk_threshold: float | None = Field(default=None, ge=0, le=1)

# Fields that may be cleared with an explicit null (all others ignore null)
NULLABLE_FIELDS = {"description", "venue_latitude", "venue_longitude", "venue_name"}

# Allowed status changes: scheduled -> active -> closed, and anything -> cancelled
TRANSITIONS = {
    "scheduled": {"active", "cancelled"},
    "active": {"closed", "cancelled"},
    "closed": {"cancelled"},
    "cancelled": set(),
}

def status_value(value) -> str:
    return value.value if isinstance(value, SessionStatus) else str(value)

def get_session_or_404(session_id: str, db: Session) -> Sessions:
    session = db.query(Sessions).filter(Sessions.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return session

def require_owner(user: Users, session: Sessions) -> None:
    if user.role != "admin" and session.instructor_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

def check_windows(start: datetime, end: datetime, opens: datetime, closes: datetime) -> None:
    if as_utc(end) <= as_utc(start):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="scheduled_end must be after scheduled_start")
    if as_utc(closes) <= as_utc(opens):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="checkin_closes_at must be after checkin_opens_at")

def to_detail(session: Sessions) -> resp_session:
    return resp_session(
        id=session.id,
        course_id=session.course_id,
        instructor_id=session.instructor_id,
        name=session.name,
        session_type=session.session_type,
        description=session.description,
        status=status_value(session.status),
        scheduled_start=session.scheduled_start,
        scheduled_end=session.scheduled_end,
        checkin_opens_at=session.checkin_opens_at,
        checkin_closes_at=session.checkin_closes_at,
        venue_latitude=session.venue_latitude,
        venue_longitude=session.venue_longitude,
        venue_name=session.venue_name,
        geofence_radius_meters=session.geofence_radius_meters,
        require_liveness_check=session.require_liveness_check,
        require_face_match=session.require_face_match,
        risk_threshold=session.risk_threshold,
        qr_code_enabled=session.qr_code_secret is not None,
        created_at=session.created_at,
    )

def to_summaries(sessions: list[Sessions], db: Session) -> list[resp_session_summary]:
    if not sessions:
        return []

    course_ids = {s.course_id for s in sessions}
    session_ids = [s.id for s in sessions]

    courses = {c.id: c for c in db.query(Courses).filter(Courses.id.in_(course_ids)).all()}
    enrolled = dict(
        db.query(Enrollments.course_id, func.count(Enrollments.id))
        .filter(Enrollments.course_id.in_(course_ids), Enrollments.is_active.is_(True))
        .group_by(Enrollments.course_id)
        .all()
    )
    checked_in = dict(
        db.query(CheckIns.session_id, func.count(CheckIns.id))
        .filter(CheckIns.session_id.in_(session_ids), CheckIns.status != CheckInStatus.REJECTED)
        .group_by(CheckIns.session_id)
        .all()
    )

    return [
        resp_session_summary(
            id=s.id,
            course_id=s.course_id,
            course_code=courses[s.course_id].code,
            course_name=courses[s.course_id].name,
            instructor_id=s.instructor_id,
            name=s.name,
            session_type=s.session_type,
            status=status_value(s.status),
            scheduled_start=s.scheduled_start,
            scheduled_end=s.scheduled_end,
            checkin_opens_at=s.checkin_opens_at,
            checkin_closes_at=s.checkin_closes_at,
            venue_name=s.venue_name,
            total_enrolled=enrolled.get(s.course_id, 0),
            checked_in_count=checked_in.get(s.id, 0),
        )
        for s in sessions
    ]

# GET /sessions/ - List sessions (instructor/admin)
@routers.get("/", response_model=Page[resp_session_summary], status_code=status.HTTP_200_OK)
def list_sessions(
    status_filter: StatusName | None = Query(default=None, alias="status"),
    course_id: str | None = Query(default=None, max_length=36),
    instructor_id: str | None = Query(default=None, max_length=36),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: Users = Depends(require_role("admin", "instructor")),
    db: Session = Depends(get_db),
):
    query = db.query(Sessions)

    if status_filter is not None:
        query = query.filter(Sessions.status == SessionStatus(status_filter))
    if course_id:
        query = query.filter(Sessions.course_id == course_id)
    if instructor_id:
        query = query.filter(Sessions.instructor_id == instructor_id)
    if start_date is not None:
        query = query.filter(Sessions.scheduled_start >= as_utc(start_date))
    if end_date is not None:
        query = query.filter(Sessions.scheduled_start <= as_utc(end_date))

    total = query.count()
    items = query.order_by(Sessions.scheduled_start.desc()).offset(offset).limit(limit).all()

    return Page[resp_session_summary](items=to_summaries(items, db), total=total, limit=limit, offset=offset)

# GET /sessions/active - Currently open sessions (public, no auth)
@routers.get("/active", response_model=list[resp_active_session], status_code=status.HTTP_200_OK)
def active_sessions(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Sessions, Courses)
        .join(Courses, Courses.id == Sessions.course_id)
        .filter(
            Sessions.status == SessionStatus.ACTIVE,
        )
        .order_by(Sessions.scheduled_start)
        .limit(100)
        .all()
    )

    return [
        resp_active_session(
            id=s.id,
            course_id=s.course_id,
            course_code=c.code,
            name=s.name,
            status=status_value(s.status),
            scheduled_start=s.scheduled_start,
            scheduled_end=s.scheduled_end,
            checkin_opens_at=s.checkin_opens_at,
            checkin_closes_at=s.checkin_closes_at,
            venue_name=s.venue_name,
        )
        for s, c in rows
    ]

# GET /sessions/my-sessions - Sessions relevant to the current user
@routers.get("/my-sessions", response_model=list[resp_session_summary], status_code=status.HTTP_200_OK)
def my_sessions(
    status_filter: StatusName | None = Query(default=None, alias="status"),
    upcoming: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Sessions)

    if user.role == "student":
        enrolled_courses = db.query(Enrollments.course_id).filter(Enrollments.student_id == user.id, Enrollments.is_active.is_(True))
        query = query.filter(Sessions.course_id.in_(enrolled_courses))
    elif user.role != "admin":
        query = query.filter(Sessions.instructor_id == user.id)

    if status_filter is not None:
        query = query.filter(Sessions.status == SessionStatus(status_filter))
    if upcoming:
        query = query.filter(Sessions.scheduled_start > datetime.now(timezone.utc)).order_by(Sessions.scheduled_start.asc())
    else:
        query = query.order_by(Sessions.scheduled_start.desc())

    return to_summaries(query.limit(limit).all(), db)

# GET /sessions/{session_id} - Session details
@routers.get("/{session_id}", response_model=resp_session, status_code=status.HTTP_200_OK)
def read_session(session_id: str, user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    return to_detail(get_session_or_404(session_id, db))

# POST /sessions/ - Create session (instructor)
@routers.post("/", response_model=resp_session, status_code=status.HTTP_201_CREATED)
def add_session(body: create_session, request: Request, user: Users = Depends(require_role("admin", "instructor")), db: Session = Depends(get_db)):
    course = db.query(Courses).filter(Courses.id == body.course_id, Courses.is_active.is_(True)).first()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    start = as_utc(body.scheduled_start)
    if start <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="scheduled_start must be in the future")

    opens = as_utc(body.checkin_opens_at) if body.checkin_opens_at else start - timedelta(minutes=15)
    closes = as_utc(body.checkin_closes_at) if body.checkin_closes_at else start + timedelta(minutes=30)
    check_windows(start, body.scheduled_end, opens, closes)

    # Venue and security settings fall back to the course defaults
    session = Sessions(
        course_id=course.id,
        instructor_id=user.id,
        name=body.name,
        session_type=body.session_type,
        description=body.description,
        scheduled_start=start,
        scheduled_end=as_utc(body.scheduled_end),
        checkin_opens_at=opens,
        checkin_closes_at=closes,
        status=SessionStatus.SCHEDULED,
        venue_latitude=body.venue_latitude if body.venue_latitude is not None else course.venue_latitude,
        venue_longitude=body.venue_longitude if body.venue_longitude is not None else course.venue_longitude,
        venue_name=body.venue_name if body.venue_name is not None else course.venue_name,
        geofence_radius_meters=body.geofence_radius_meters if body.geofence_radius_meters is not None else course.geofence_radius_meters,
        require_liveness_check=body.require_liveness_check,
        require_face_match=body.require_face_match,
        risk_threshold=body.risk_threshold if body.risk_threshold is not None else course.risk_threshold,
    )
    db.add(session)
    db.flush()

    write_audit(db, request, user.id, AuditAction.SESSION_CREATED, "session", session.id, {"course_id": course.id, "name": session.name})
    db.commit()
    db.refresh(session)

    return to_detail(session)

# PATCH /sessions/{session_id} - Update session
@routers.patch("/{session_id}", response_model=resp_session, status_code=status.HTTP_200_OK)
def edit_session(session_id: str, body: update_session, request: Request, user: Users = Depends(require_role("admin", "instructor")), db: Session = Depends(get_db)):
    session = get_session_or_404(session_id, db)
    require_owner(user, session)

    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None or k in NULLABLE_FIELDS}

    new_status = data.pop("status", None)
    current_status = status_value(session.status)
    if new_status is not None and new_status != current_status:
        if new_status not in TRANSITIONS[current_status]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot change status from {current_status} to {new_status}")

    for field in ("scheduled_start", "scheduled_end", "checkin_opens_at", "checkin_closes_at"):
        if field in data:
            data[field] = as_utc(data[field])

    check_windows(
        data.get("scheduled_start", session.scheduled_start),
        data.get("scheduled_end", session.scheduled_end),
        data.get("checkin_opens_at", session.checkin_opens_at),
        data.get("checkin_closes_at", session.checkin_closes_at),
    )

    for field, value in data.items():
        setattr(session, field, value)

    if new_status is not None and new_status != current_status:
        now = datetime.now(timezone.utc)
        session.status = SessionStatus(new_status)
        if new_status == "active":
            session.actual_start = now
        elif new_status == "closed":
            session.actual_end = now

    write_audit(db, request, user.id, AuditAction.SESSION_UPDATED, "session", session.id,
                {"fields": sorted(data), "status": new_status if new_status != current_status else None})
    db.commit()
    db.refresh(session)

    return to_detail(session)

# DELETE /sessions/{session_id} - Delete session
@routers.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_session(session_id: str, request: Request, user: Users = Depends(require_role("admin", "instructor")), db: Session = Depends(get_db)):
    session = get_session_or_404(session_id, db)
    require_owner(user, session)

    if status_value(session.status) != "scheduled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only scheduled sessions can be deleted; cancel it instead")
    if db.query(CheckIns.id).filter(CheckIns.session_id == session.id).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session has check-ins; cancel it instead")

    write_audit(db, request, user.id, AuditAction.SESSION_DELETED, "session", session.id, {"course_id": session.course_id, "name": session.name})
    db.delete(session)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
