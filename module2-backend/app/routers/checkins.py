import base64
import binascii
import hmac
import html
import json

from datetime import datetime, timedelta, timezone
from enum import Enum
from fastapi import APIRouter, Depends, status, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.models import (
    AuditAction, CheckIns, CheckInStatus, Courses, Devices, Enrollments, Risk_Signals,
    SessionStatus, Sessions, Users,
)
from app.geo import client_ip, coordinates_in_singapore, is_singapore_ip, parse_ip
from app.ratelimit import CHECKIN_PER_MINUTE, MINUTE, enforce
from app.metrics import CHECKIN_ATTEMPTS, CHECKIN_SUCCESS
from app.retention import deletion_date
from app.risk import assess_risk
from app.routers.security import require_role
from app.utils import Page, as_utc, require_course_access, write_audit

# -----------------------------------------------------------------------------
# Check-in Endpoints (checkins.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/checkins", tags=["checkins"])

# Models
MAX_FRAMES = 10
MAX_FRAME_CHARS = 2_000_000

def check_image(value: str) -> str:
    try:
        raw = base64.b64decode(value.split(",", 1)[-1], validate=True)  # Tolerates a data: URI prefix
    except (binascii.Error, ValueError):
        raise ValueError("liveness images must be base64")
    if not (raw.startswith(b"\x89PNG\r\n\x1a\n") or raw.startswith(b"\xff\xd8\xff")):
        raise ValueError("liveness images must be PNG or JPEG")
    return value

class create_checkin(BaseModel):
    session_id: str = Field(min_length=1, max_length=36)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_accuracy_meters: float | None = Field(default=None, ge=0, le=100000)
    device_fingerprint: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[\w.\-:]+$")
    liveness_challenge_response: str | None = Field(default=None, max_length=8_000_000)  # Single frame
    liveness_frames: list[str] | None = Field(default=None, min_length=1, max_length=MAX_FRAMES)  # Ordered frames of a blink / head_turn clip
    qr_code: str | None = Field(default=None, max_length=256)
    liveness_challenge_type: Literal["passive", "blink", "head_turn"] = "passive"

    @field_validator("liveness_challenge_response")
    def single_must_be_image(cls, value):
        return check_image(value) if value is not None else value

    @field_validator("liveness_frames")
    def frames_must_be_images(cls, frames):
        if frames is None:
            return frames
        if any(len(f) > MAX_FRAME_CHARS for f in frames):
            raise ValueError("a liveness frame is too large")
        return [check_image(f) for f in frames]

    @property
    def frames(self) -> list[str]:
        # One list for everything downstream: the multi-frame field wins, otherwise the single image
        return self.liveness_frames or ([self.liveness_challenge_response] if self.liveness_challenge_response else [])

class resp_base(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("status", mode="before", check_fields=False)
    def status_text(cls, value):
        return value.value if isinstance(value, Enum) else value

class resp_risk_factor(BaseModel):
    type: str
    signal_type: str | None = None
    severity: str | None = None
    confidence: float = 1.0
    weight: float
    details: dict | str | None = None

    @model_validator(mode="after")
    def mirror_type(self):
        self.signal_type = self.signal_type or self.type
        return self

class resp_with_factors(resp_base):
    risk_factors: list[resp_risk_factor] = []

    @field_validator("risk_factors", mode="before")
    def load_factors(cls, value):
        # Stored as JSON text on the row
        try:
            return json.loads(value) if isinstance(value, str) else (value or [])
        except ValueError:
            return []

class resp_checkin(resp_with_factors):
    id: str
    session_id: str
    student_id: str
    status: str
    checked_in_at: datetime
    latitude: float | None = None
    longitude: float | None = None
    distance_from_venue_meters: float | None = None
    liveness_passed: bool | None = None
    liveness_score: float | None = None
    risk_score: float

class resp_checkin_full(resp_checkin):
    device_id: str | None = None
    location_accuracy_meters: float | None = None
    face_match_passed: bool | None = None
    face_match_score: float | None = None
    qr_code_verified: bool | None = None
    reviewed_by_id: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    appeal_reason: str | None = None
    appealed_at: datetime | None = None

    # XSS Prevention
    @field_serializer("review_notes", "appeal_reason")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

class resp_checkin_list_item(resp_base):
    id: str
    session_id: str
    session_name: str
    student_id: str
    student_name: str
    student_email: str
    status: str
    checked_in_at: datetime
    distance_from_venue_meters: float | None = None
    risk_score: float
    liveness_passed: bool | None = None

    # XSS Prevention
    @field_serializer("session_name", "student_name")
    def escape_text(self, value: str) -> str:
        return html.escape(value)

class resp_my_checkin(resp_base):
    id: str
    session_id: str
    session_name: str
    course_code: str
    status: str
    checked_in_at: datetime
    risk_score: float

    # XSS Prevention
    @field_serializer("session_name", "course_code")
    def escape_text(self, value: str) -> str:
        return html.escape(value)

class resp_session_checkin(resp_with_factors):
    id: str
    student_id: str
    student_name: str
    student_email: str
    status: str
    checked_in_at: datetime
    distance_from_venue_meters: float | None = None
    risk_score: float
    liveness_passed: bool | None = None
    device_trusted: bool | None = None

    # XSS Prevention
    @field_serializer("student_name")
    def escape_text(self, value: str) -> str:
        return html.escape(value)

class resp_flagged_checkin(resp_with_factors):
    id: str
    session_id: str
    session_name: str
    student_id: str
    student_name: str
    status: str
    checked_in_at: datetime
    risk_score: float
    appeal_reason: str | None = None
    appealed_at: datetime | None = None

    # XSS Prevention
    @field_serializer("session_name", "student_name", "appeal_reason")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

class create_appeal(BaseModel):
    appeal_reason: str = Field(min_length=1, max_length=2000)

    @field_validator("appeal_reason")
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("appeal_reason must not be blank")
        return value

class resp_appeal(resp_base):
    id: str
    status: str
    appeal_reason: str | None = None
    appealed_at: datetime | None = None

    # XSS Prevention
    @field_serializer("appeal_reason")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

class create_review(BaseModel):
    status: Literal["approved", "rejected"]
    review_notes: str | None = Field(default=None, max_length=2000)

class resp_review(resp_base):
    id: str
    status: str
    reviewed_by_id: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None

    # XSS Prevention
    @field_serializer("review_notes")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

# Helpers
APPEAL_WINDOW = timedelta(days=7)

def refuse(db: Session, request: Request, user: Users, session_id: str, reason: str, detail: str, code: int = 400,
           actions: tuple = (AuditAction.CHECKIN_ATTEMPTED,), extra: dict | None = None):
    # Refused attempts are audited, so commit before raising (an exception would roll the entry back)
    for action in actions:
        write_audit(db, request, user.id, action, "session", session_id, {"reason": reason, **(extra or {})}, success=False)
    db.commit()
    raise HTTPException(status_code=code, detail=detail)

# POST /checkins - Submit check-in
@routers.post("/", response_model=resp_checkin, status_code=status.HTTP_201_CREATED)
def submit_checkin(body: create_checkin, request: Request, student: Users = Depends(require_role("student")), db: Session = Depends(get_db)):
    CHECKIN_ATTEMPTS.inc()  # Every submission counts, including refused and rate-limited ones
    enforce("checkin", student.id, CHECKIN_PER_MINUTE, MINUTE)

    session = db.query(Sessions).filter(Sessions.id == body.session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    sid, now = session.id, datetime.now(timezone.utc)

    # Singapore only: reject when the client's public IP resolves outside Singapore.
    # Private/local addresses are treated as on-campus and allowed.
    if not is_singapore_ip(parse_ip(client_ip(request))):
        refuse(db, request, student, sid, "ip_outside_singapore", "Check-ins are only allowed from Singapore", 403,
               (AuditAction.SECURITY_VIOLATION, AuditAction.CHECKIN_REJECTED), {"ip": client_ip(request)})

    # Singapore only: reject GPS coordinates outside Singapore.
    # The submitted coordinates are only checked here; they are stored only with geolocation consent.
    if not coordinates_in_singapore(body.latitude, body.longitude):
        refuse(db, request, student, sid, "gps_outside_singapore", "Check-ins are only allowed from Singapore", 403,
               (AuditAction.SECURITY_VIOLATION, AuditAction.CHECKIN_REJECTED), {"ip": client_ip(request)})

    # Session must be open, the student enrolled, and not already checked in
    if session.status != SessionStatus.ACTIVE:
        refuse(db, request, student, sid, "session_not_active", "Session is not active")
    if not as_utc(session.checkin_opens_at) <= now <= as_utc(session.checkin_closes_at):
        refuse(db, request, student, sid, "window_closed", "Check-in window is closed")
    if db.query(CheckIns.id).filter(CheckIns.session_id == sid, CheckIns.student_id == student.id).first() is not None:
        refuse(db, request, student, sid, "duplicate", "Already checked in")

    # Optional QR code (only enforced when the session has one)
    if session.qr_code_secret:
        expired = session.qr_code_expires_at and now > as_utc(session.qr_code_expires_at)
        if not body.qr_code or not hmac.compare_digest(body.qr_code, session.qr_code_secret) or expired:
            refuse(db, request, student, sid, "invalid_qr", "Invalid or expired QR code")

    # Camera consent is needed before any image is processed
    if body.frames and not student.camera_consent:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Camera consent not given")

    risk = assess_risk(db, student, session, body.latitude, body.longitude, body.location_accuracy_meters, body.device_fingerprint, body.frames, request, body.liveness_challenge_type)
    own_device, location, face = risk.device, risk.location, risk.face

    checkin = CheckIns(
        session_id=sid, student_id=student.id, device_id=own_device.id if own_device else None, status=risk.status, checked_in_at=now,
        latitude=location.latitude, longitude=location.longitude, distance_from_venue_meters=location.distance,
        location_accuracy_meters=body.location_accuracy_meters if student.geolocation_consent else None,
        liveness_passed=face.liveness_passed, liveness_score=face.liveness_score, liveness_challenge_type=body.liveness_challenge_type if face.liveness_passed is not None else None,
        face_match_passed=face.match_passed, face_match_score=face.match_score, risk_score=risk.risk_score,
        risk_factors=risk.risk_factors_json,
        qr_code_verified=bool(session.qr_code_secret), scheduled_deletion_at=deletion_date(now),
    )
    db.add(checkin)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already checked in")

    for signal in risk.signals:
        db.add(Risk_Signals(checkin_id=checkin.id, signal_type=signal.type, severity=signal.severity, weight=signal.weight, details=json.dumps(signal.details) if signal.details is not None else None))
    if own_device is not None:
        own_device.total_checkins = (own_device.total_checkins or 0) + 1

    device_id = checkin.device_id
    write_audit(db, request, student.id, AuditAction.CHECKIN_ATTEMPTED, "checkin", checkin.id, {"session_id": sid, "distance_m": location.distance}, device_id=device_id)
    write_audit(db, request, student.id, risk.audit_action, "checkin", checkin.id, {"session_id": sid, "risk_score": risk.risk_score, "status": risk.status.value}, device_id=device_id)
    db.commit()
    db.refresh(checkin)
    if risk.status == CheckInStatus.APPROVED:
        CHECKIN_SUCCESS.inc()

    return resp_checkin.model_validate(checkin)

# GET /checkins - List check-ins (with filters)
@routers.get("/", response_model=Page[resp_checkin_list_item], status_code=status.HTTP_200_OK)
def list_checkins(
    session_id: str | None = Query(default=None, max_length=36),
    course_id: str | None = Query(default=None, max_length=36),
    student_id: str | None = Query(default=None, max_length=36),
    status_filter: Literal["pending", "approved", "flagged", "rejected", "appealed"] | None = Query(default=None, alias="status"),
    min_risk_score: float | None = Query(default=None, ge=0, le=1),
    max_risk_score: float | None = Query(default=None, ge=0, le=1),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: Users = Depends(require_role("admin", "instructor")),
    db: Session = Depends(get_db),
):
    query = db.query(CheckIns, Sessions, Users).join(Sessions, Sessions.id == CheckIns.session_id).join(Users, Users.id == CheckIns.student_id)

    # Instructors only see courses they run a session for; admins see everything
    if user.role != "admin":
        query = query.filter(Sessions.course_id.in_(db.query(Sessions.course_id).filter(Sessions.instructor_id == user.id)))

    start = as_utc(start_date) if start_date else None
    end = as_utc(end_date) if end_date else None
    # (is the filter used, how to build it) - built lazily because comparing a column with None raises
    filters = [
        (bool(session_id), lambda: CheckIns.session_id == session_id),
        (bool(course_id), lambda: Sessions.course_id == course_id),
        (bool(student_id), lambda: CheckIns.student_id == student_id),
        (bool(status_filter), lambda: CheckIns.status == CheckInStatus(status_filter)),
        (min_risk_score is not None, lambda: CheckIns.risk_score >= min_risk_score),
        (max_risk_score is not None, lambda: CheckIns.risk_score <= max_risk_score),
        (start is not None, lambda: CheckIns.checked_in_at >= start),
        (end is not None, lambda: CheckIns.checked_in_at <= end),
    ]
    query = query.filter(*[build() for used, build in filters if used])

    total = query.count()
    rows = query.order_by(CheckIns.checked_in_at.desc()).offset(offset).limit(limit).all()

    items = [
        resp_checkin_list_item(
            id=c.id, session_id=c.session_id, session_name=s.name, student_id=u.id, student_name=u.full_name, student_email=u.email,
            status=c.status, checked_in_at=c.checked_in_at, distance_from_venue_meters=c.distance_from_venue_meters,
            risk_score=c.risk_score, liveness_passed=c.liveness_passed,
        )
        for c, s, u in rows
    ]
    return Page[resp_checkin_list_item](items=items, total=total, limit=limit, offset=offset)

# GET /checkins/my-checkins - Student's own check-ins
@routers.get("/my-checkins", response_model=list[resp_my_checkin], status_code=status.HTTP_200_OK)
def my_checkins(
    course_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=100),
    student: Users = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    query = (
        db.query(CheckIns, Sessions, Courses)
        .join(Sessions, Sessions.id == CheckIns.session_id)
        .join(Courses, Courses.id == Sessions.course_id)
        .filter(CheckIns.student_id == student.id)
    )
    if course_id:
        query = query.filter(Sessions.course_id == course_id)

    return [
        resp_my_checkin(id=c.id, session_id=c.session_id, session_name=s.name, course_code=course.code, status=c.status, checked_in_at=c.checked_in_at, risk_score=c.risk_score)
        for c, s, course in query.order_by(CheckIns.checked_in_at.desc()).limit(limit).all()
    ]

# GET /checkins/session/{session_id} - Check-ins for a session
@routers.get("/session/{session_id}", response_model=list[resp_session_checkin], status_code=status.HTTP_200_OK)
def session_checkins(session_id: str, user: Users = Depends(require_role("admin", "instructor", "ta")), db: Session = Depends(get_db)):
    session = db.query(Sessions).filter(Sessions.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    require_course_access(user, session.course_id, db)

    rows = (
        db.query(CheckIns, Users, Devices)
        .join(Users, Users.id == CheckIns.student_id)
        .outerjoin(Devices, Devices.id == CheckIns.device_id)
        .filter(CheckIns.session_id == session.id)
        .order_by(CheckIns.checked_in_at.desc())
        .all()
    )
    return [
        resp_session_checkin(
            id=c.id, student_id=u.id, student_name=u.full_name, student_email=u.email, status=c.status, checked_in_at=c.checked_in_at,
            distance_from_venue_meters=c.distance_from_venue_meters, risk_score=c.risk_score, risk_factors=c.risk_factors,
            liveness_passed=c.liveness_passed, device_trusted=d.is_trusted if d is not None else None,
        )
        for c, u, d in rows
    ]

# GET /checkins/flagged - Flagged check-ins
@routers.get("/flagged", response_model=Page[resp_flagged_checkin], status_code=status.HTTP_200_OK)
def flagged_checkins(
    course_id: str | None = Query(default=None, max_length=36),
    session_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: Users = Depends(require_role("admin", "instructor", "ta")),
    db: Session = Depends(get_db),
):
    query = (
        db.query(CheckIns, Sessions, Users)
        .join(Sessions, Sessions.id == CheckIns.session_id)
        .join(Users, Users.id == CheckIns.student_id)
        .filter(CheckIns.status.in_([CheckInStatus.FLAGGED, CheckInStatus.APPEALED]))
    )

    # Instructors only see courses they run a session for; admins see everything
    if user.role != "admin":
        query = query.filter(Sessions.course_id.in_(db.query(Sessions.course_id).filter(Sessions.instructor_id == user.id)))
    if course_id:
        query = query.filter(Sessions.course_id == course_id)
    if session_id:
        query = query.filter(CheckIns.session_id == session_id)

    total = query.count()
    rows = query.order_by(CheckIns.checked_in_at.desc()).offset(offset).limit(limit).all()
    items = [
        resp_flagged_checkin(
            id=c.id, session_id=c.session_id, session_name=s.name, student_id=u.id, student_name=u.full_name, status=c.status,
            checked_in_at=c.checked_in_at, risk_score=c.risk_score, risk_factors=c.risk_factors,
            appeal_reason=c.appeal_reason, appealed_at=c.appealed_at,
        )
        for c, s, u in rows
    ]
    return Page[resp_flagged_checkin](items=items, total=total, limit=limit, offset=offset)

# GET /checkins/{checkin_id} - Check-in detail
@routers.get("/{checkin_id}", response_model=resp_checkin_full, status_code=status.HTTP_200_OK)
def read_checkin(checkin_id: str, user: Users = Depends(require_role("admin", "instructor", "ta", "student")), db: Session = Depends(get_db)):
    checkin = db.query(CheckIns).filter(CheckIns.id == checkin_id).first()
    if checkin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    # Students may only read their own check-ins; staff need access to the session's course
    if user.role == "student":
        if checkin.student_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    else:
        require_course_access(user, db.query(Sessions.course_id).filter(Sessions.id == checkin.session_id).scalar(), db)

    return resp_checkin_full.model_validate(checkin)

# POST /checkins/{checkin_id}/appeal - Student appeals a check-in
@routers.post("/{checkin_id}/appeal", response_model=resp_appeal, status_code=status.HTTP_200_OK)
def appeal_checkin(checkin_id: str, body: create_appeal, request: Request, student: Users = Depends(require_role("student")), db: Session = Depends(get_db)):
    checkin = db.query(CheckIns).filter(CheckIns.id == checkin_id).first()
    if checkin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if checkin.student_id != student.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    now = datetime.now(timezone.utc)
    if checkin.appealed_at is not None or checkin.status == CheckInStatus.APPEALED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Check-in has already been appealed")
    if checkin.status not in (CheckInStatus.REJECTED, CheckInStatus.FLAGGED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only rejected or flagged check-ins can be appealed")
    if now - as_utc(checkin.checked_in_at) > APPEAL_WINDOW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appeal window has closed")

    previous = checkin.status
    checkin.status = CheckInStatus.APPEALED
    checkin.appeal_reason = body.appeal_reason
    checkin.appealed_at = now
    write_audit(db, request, student.id, AuditAction.CHECKIN_APPEALED, "checkin", checkin.id, {"session_id": checkin.session_id, "previous_status": previous.value}, device_id=checkin.device_id)
    db.commit()
    db.refresh(checkin)

    return resp_appeal.model_validate(checkin)

# POST /checkins/{checkin_id}/review - Instructor reviews an appeal
@routers.post("/{checkin_id}/review", response_model=resp_review, status_code=status.HTTP_200_OK)
def review_checkin(checkin_id: str, body: create_review, request: Request, user: Users = Depends(require_role("admin", "instructor", "ta")), db: Session = Depends(get_db)):
    checkin = db.query(CheckIns).filter(CheckIns.id == checkin_id).first()
    if checkin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    require_course_access(user, db.query(Sessions.course_id).filter(Sessions.id == checkin.session_id).scalar(), db)

    if checkin.status not in (CheckInStatus.FLAGGED, CheckInStatus.APPEALED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only flagged or appealed check-ins can be reviewed")

    previous = checkin.status
    checkin.status = CheckInStatus(body.status)
    checkin.reviewed_by_id = user.id
    checkin.reviewed_at = datetime.now(timezone.utc)
    checkin.review_notes = body.review_notes
    write_audit(db, request, user.id, AuditAction.CHECKIN_REVIEWED, "checkin", checkin.id,
                {"session_id": checkin.session_id, "previous_status": previous.value, "status": body.status}, device_id=checkin.device_id)
    db.commit()
    db.refresh(checkin)

    return resp_review.model_validate(checkin)