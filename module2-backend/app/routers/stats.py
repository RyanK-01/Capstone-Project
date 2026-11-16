import html

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, status, HTTPException, Query
from pydantic import BaseModel, field_serializer
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CheckIns, CheckInStatus, Courses, Enrollments, SessionStatus, Sessions, Users
from app.routers.security import require_role
from app.routers.users import can_view_user
from app.utils import as_utc, require_course_access, taught_by

# -----------------------------------------------------------------------------
# Statistics Endpoints (stats.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/stats", tags=["stats"])

# Attendance counts every check-in that was not rejected
NOT_REJECTED = CheckIns.status != CheckInStatus.REJECTED
PENDING_REVIEW = [CheckInStatus.FLAGGED, CheckInStatus.APPEALED]
HIGH_RISK = 0.5
LOW_ATTENDANCE_RATE = 0.75

# Models
class resp_overview(BaseModel):
    total_sessions: int
    active_sessions: int
    total_courses: int
    total_students: int
    today_checkins: int
    total_checkins_today: int
    total_checkins_week: int
    average_attendance_rate: float
    flagged_pending: int
    flagged_pending_review: int
    approval_rate: float
    average_risk_score: float
    high_risk_checkins_today: int
    trends: dict

class resp_session_stats(BaseModel):
    session_id: str
    session_name: str
    course_code: str
    scheduled_start: datetime
    status: str
    total_enrolled: int
    checked_in: int
    checked_in_count: int
    approved_count: int
    flagged_count: int
    rejected_count: int
    pending_count: int
    attendance_rate: float
    by_status: dict[str, int]
    average_risk_score: float
    average_distance_meters: float
    average_checkin_time_minutes: float
    risk_distribution: dict[str, int]
    checkin_timeline: list[dict]

    # XSS Prevention
    @field_serializer("session_name", "course_code")
    def escape_text(self, value: str) -> str:
        return html.escape(value)

class resp_course_stats(BaseModel):
    course_id: str
    course_code: str
    course_name: str
    total_sessions: int
    total_enrolled: int
    overall_attendance_rate: float
    average_attendance_rate: float
    flagged_checkins: int
    sessions: list[dict]
    student_attendance: list[dict]
    low_attendance_alerts: list[dict]

    # XSS Prevention
    @field_serializer("course_code", "course_name")
    def escape_text(self, value: str) -> str:
        return html.escape(value)

class resp_student_stats(BaseModel):
    student_id: str
    student_name: str
    student_email: str
    total_enrolled_courses: int
    total_sessions: int
    attended_sessions: int
    attendance_rate: float
    courses: list[dict]
    recent_sessions: list[dict]
    recent_checkins: list[dict]

    # XSS Prevention
    @field_serializer("student_name")
    def escape_text(self, value: str) -> str:
        return html.escape(value)

def rate(part: int, whole: int) -> float:
    return round(min(part / whole, 1.0), 4) if whole else 0.0

def average(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0

def esc(value: str | None) -> str | None:
    return html.escape(value) if value is not None else None

def status_name(value) -> str:
    return value.value if hasattr(value, "value") else str(value)

# GET /stats/overview - System overview
@routers.get("/overview", response_model=resp_overview, status_code=status.HTTP_200_OK)
def overview(
    course_id: str | None = Query(default=None, max_length=36),
    days: int = Query(default=7, ge=1, le=90),
    user: Users = Depends(require_role("admin", "instructor")),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = today_start - timedelta(days=days - 1)

    sessions_q = db.query(Sessions)
    if user.role != "admin":
        sessions_q = sessions_q.filter(Sessions.course_id.in_(db.query(Sessions.course_id).filter(Sessions.instructor_id == user.id)))
    if course_id:
        if user.role != "admin":
            require_course_access(user, course_id, db)
        sessions_q = sessions_q.filter(Sessions.course_id == course_id)

    sessions = sessions_q.with_entities(Sessions.id, Sessions.course_id, Sessions.status, Sessions.scheduled_start).all()
    course_ids = {s.course_id for s in sessions}
    if user.role == "admin" and not course_id:
        total_courses = db.query(Courses.id).filter(Courses.is_active.is_(True)).count()
        total_students = db.query(Users.id).filter(Users.role == "student", Users.is_active.is_(True)).count()
    else:
        total_courses = len(course_ids)
        total_students = (
            db.query(func.count(func.distinct(Enrollments.student_id)))
            .filter(Enrollments.course_id.in_(course_ids), Enrollments.is_active.is_(True))
            .scalar() or 0
        ) if course_ids else 0

    enrolled = dict(
        db.query(Enrollments.course_id, func.count(Enrollments.id))
        .filter(Enrollments.course_id.in_(course_ids), Enrollments.is_active.is_(True))
        .group_by(Enrollments.course_id)
        .all()
    ) if course_ids else {}

    checkins = (
        db.query(CheckIns.status, CheckIns.risk_score, CheckIns.checked_in_at, CheckIns.session_id)
        .filter(CheckIns.session_id.in_(sessions_q.with_entities(Sessions.id)))
        .all()
    )

    # Expected attendance = enrolled students for every session that is not cancelled
    expected_total = 0
    expected_by_day: dict[str, int] = defaultdict(int)
    session_day: dict[str, str] = {}
    for s in sessions:
        day = as_utc(s.scheduled_start).date().isoformat()
        session_day[s.id] = day
        if status_name(s.status) != "cancelled":
            expected_total += enrolled.get(s.course_id, 0)
            expected_by_day[day] += enrolled.get(s.course_id, 0)

    attended_total = 0
    attended_by_day: dict[str, int] = defaultdict(int)
    count_by_day: dict[str, int] = defaultdict(int)
    approved = today = week = high_risk_today = 0
    flagged_pending = 0
    risks: list[float] = []
    for c in checkins:
        when = as_utc(c.checked_in_at)
        state = status_name(c.status)
        risks.append(c.risk_score)
        if state == "approved":
            approved += 1
        if state in ("flagged", "appealed"):
            flagged_pending += 1
        if state != "rejected":
            attended_total += 1
            attended_by_day[session_day.get(c.session_id, when.date().isoformat())] += 1
        if when >= today_start:
            today += 1
            if c.risk_score >= HIGH_RISK:
                high_risk_today += 1
        if when >= window_start:
            week += 1
            count_by_day[when.date().isoformat()] += 1

    day_keys = [(today_start - timedelta(days=i)).date().isoformat() for i in range(days)]
    trends = {
        "checkins_by_day": [{"date": d, "count": count_by_day.get(d, 0)} for d in day_keys],
        "attendance_rate_by_day": [{"date": d, "rate": rate(attended_by_day.get(d, 0), expected_by_day.get(d, 0))} for d in day_keys],
    }

    return resp_overview(
        total_sessions=len(sessions),
        active_sessions=sum(1 for s in sessions if status_name(s.status) == "active"),
        total_courses=total_courses,
        total_students=total_students,
        today_checkins=today,
        total_checkins_today=today,
        total_checkins_week=week,
        average_attendance_rate=rate(attended_total, expected_total),
        flagged_pending=flagged_pending,
        flagged_pending_review=flagged_pending,
        approval_rate=rate(approved, len(checkins)),
        average_risk_score=average(risks),
        high_risk_checkins_today=high_risk_today,
        trends=trends,
    )

# GET /stats/sessions/{session_id} - Session statistics
@routers.get("/sessions/{session_id}", response_model=resp_session_stats, status_code=status.HTTP_200_OK)
def session_stats(session_id: str, user: Users = Depends(require_role("admin", "instructor", "ta")), db: Session = Depends(get_db)):
    row = db.query(Sessions, Courses).join(Courses, Courses.id == Sessions.course_id).filter(Sessions.id == session_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    session, course = row
    require_course_access(user, course.id, db)

    total_enrolled = db.query(Enrollments.id).filter(Enrollments.course_id == course.id, Enrollments.is_active.is_(True)).count()
    checkins = db.query(CheckIns.status, CheckIns.risk_score, CheckIns.distance_from_venue_meters, CheckIns.checked_in_at).filter(CheckIns.session_id == session.id).all()

    by_status = {s.value: 0 for s in CheckInStatus}
    risk_distribution = {"low": 0, "medium": 0, "high": 0}
    minutes: list[float] = []
    timeline: dict[int, int] = defaultdict(int)
    distances: list[float] = []
    start = as_utc(session.scheduled_start)
    for c in checkins:
        by_status[status_name(c.status)] += 1
        if c.risk_score < 0.3:
            risk_distribution["low"] += 1
        elif c.risk_score < HIGH_RISK:
            risk_distribution["medium"] += 1
        else:
            risk_distribution["high"] += 1
        if c.distance_from_venue_meters is not None:
            distances.append(c.distance_from_venue_meters)
        delta = (as_utc(c.checked_in_at) - start).total_seconds() / 60
        minutes.append(delta)
        timeline[max(0, int(delta // 5) * 5)] += 1

    attended = len(checkins) - by_status["rejected"]
    return resp_session_stats(
        session_id=session.id,
        session_name=session.name,
        course_code=course.code,
        scheduled_start=session.scheduled_start,
        status=status_name(session.status),
        total_enrolled=total_enrolled,
        checked_in=attended,
        checked_in_count=attended,
        approved_count=by_status["approved"],
        flagged_count=by_status["flagged"],
        rejected_count=by_status["rejected"],
        pending_count=by_status["pending"],
        attendance_rate=rate(attended, total_enrolled),
        by_status=by_status,
        average_risk_score=average([c.risk_score for c in checkins]),
        average_distance_meters=average(distances),
        average_checkin_time_minutes=round(sum(minutes) / len(minutes), 2) if minutes else 0.0,
        risk_distribution=risk_distribution,
        checkin_timeline=[{"minute": m, "count": n} for m, n in sorted(timeline.items())],
    )

# GET /stats/courses/{course_id} - Course statistics
@routers.get("/courses/{course_id}", response_model=resp_course_stats, status_code=status.HTTP_200_OK)
def course_stats(
    course_id: str,
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    user: Users = Depends(require_role("admin", "instructor")),
    db: Session = Depends(get_db),
):
    course = db.query(Courses).filter(Courses.id == course_id).first()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    require_course_access(user, course.id, db)

    sessions_q = db.query(Sessions).filter(Sessions.course_id == course.id, Sessions.status != SessionStatus.CANCELLED)
    if start_date is not None:
        sessions_q = sessions_q.filter(Sessions.scheduled_start >= as_utc(start_date))
    if end_date is not None:
        sessions_q = sessions_q.filter(Sessions.scheduled_start <= as_utc(end_date))
    sessions = sessions_q.order_by(Sessions.scheduled_start).all()
    session_ids = [s.id for s in sessions]

    students = (
        db.query(Users)
        .join(Enrollments, Enrollments.student_id == Users.id)
        .filter(Enrollments.course_id == course.id, Enrollments.is_active.is_(True))
        .order_by(Users.full_name)
        .all()
    )
    total_enrolled = len(students)

    attended_by_session: dict[str, int] = {}
    per_student: dict[str, tuple[int, float]] = {}
    flagged = 0
    if session_ids:
        attended_by_session = dict(
            db.query(CheckIns.session_id, func.count(CheckIns.id))
            .filter(CheckIns.session_id.in_(session_ids), NOT_REJECTED)
            .group_by(CheckIns.session_id)
            .all()
        )
        per_student = {
            sid: (n, avg_risk or 0.0)
            for sid, n, avg_risk in db.query(CheckIns.student_id, func.count(CheckIns.id), func.avg(CheckIns.risk_score))
            .filter(CheckIns.session_id.in_(session_ids), NOT_REJECTED)
            .group_by(CheckIns.student_id)
            .all()
        }
        flagged = db.query(CheckIns.id).filter(CheckIns.session_id.in_(session_ids), CheckIns.status.in_(PENDING_REVIEW)).count()

    total_sessions = len(sessions)
    attended_total = sum(attended_by_session.values())
    overall = rate(attended_total, total_sessions * total_enrolled)

    student_rows, alerts = [], []
    for student in students:
        attended, avg_risk = per_student.get(student.id, (0, 0.0))
        student_rate = rate(attended, total_sessions)
        student_rows.append({
            "student_id": student.id,
            "student_name": esc(student.full_name),
            "sessions_attended": attended,
            "attendance_rate": student_rate,
            "average_risk_score": round(float(avg_risk), 4),
        })
        if total_sessions and student_rate < LOW_ATTENDANCE_RATE:
            alerts.append({
                "student_id": student.id,
                "student_name": esc(student.full_name),
                "attendance_rate": student_rate,
                "sessions_missed": total_sessions - attended,
            })

    return resp_course_stats(
        course_id=course.id,
        course_code=course.code,
        course_name=course.name,
        total_sessions=total_sessions,
        total_enrolled=total_enrolled,
        overall_attendance_rate=overall,
        average_attendance_rate=overall,
        flagged_checkins=flagged,
        sessions=[
            {
                "session_id": s.id,
                "name": esc(s.name),
                "date": as_utc(s.scheduled_start).date().isoformat(),
                "attendance_rate": rate(attended_by_session.get(s.id, 0), total_enrolled),
                "checked_in": attended_by_session.get(s.id, 0),
            }
            for s in sessions
        ],
        student_attendance=student_rows,
        low_attendance_alerts=alerts,
    )

# GET /stats/students/{student_id} - Student statistics
@routers.get("/students/{student_id}", response_model=resp_student_stats, status_code=status.HTTP_200_OK)
def student_stats(student_id: str, user: Users = Depends(require_role("admin", "instructor")), db: Session = Depends(get_db)):
    student = db.query(Users).filter(Users.id == student_id).first()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if not can_view_user(user, student, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    # Instructors only see the courses they run; admins see everything
    courses_q = (
        db.query(Courses)
        .join(Enrollments, Enrollments.course_id == Courses.id)
        .filter(Enrollments.student_id == student.id, Enrollments.is_active.is_(True))
    )
    if user.role != "admin":
        courses_q = courses_q.filter(taught_by(user, Courses.id))
    courses = courses_q.order_by(Courses.code).all()
    course_ids = [c.id for c in courses]

    # Sessions the student could have attended: already open or finished
    held = [SessionStatus.ACTIVE, SessionStatus.CLOSED]
    sessions_by_course: dict[str, int] = {}
    attended_by_course: dict[str, tuple[int, float]] = {}
    if course_ids:
        sessions_by_course = dict(
            db.query(Sessions.course_id, func.count(Sessions.id))
            .filter(Sessions.course_id.in_(course_ids), Sessions.status.in_(held))
            .group_by(Sessions.course_id)
            .all()
        )
        attended_by_course = {
            cid: (n, avg_risk or 0.0)
            for cid, n, avg_risk in db.query(Sessions.course_id, func.count(CheckIns.id), func.avg(CheckIns.risk_score))
            .join(CheckIns, CheckIns.session_id == Sessions.id)
            .filter(Sessions.course_id.in_(course_ids), CheckIns.student_id == student.id, NOT_REJECTED)
            .group_by(Sessions.course_id)
            .all()
        }

    course_rows = []
    for c in courses:
        total = sessions_by_course.get(c.id, 0)
        attended, avg_risk = attended_by_course.get(c.id, (0, 0.0))
        course_rows.append({
            "course_id": c.id,
            "course_code": esc(c.code),
            "attendance_rate": rate(attended, total),
            "sessions_attended": attended,
            "total_sessions": total,
            "average_risk_score": round(float(avg_risk), 4),
        })

    recent = []
    if course_ids:
        recent = [
            {"session_name": esc(s.name), "course_code": esc(c.code), "checked_in_at": ck.checked_in_at, "status": status_name(ck.status)}
            for ck, s, c in db.query(CheckIns, Sessions, Courses)
            .join(Sessions, Sessions.id == CheckIns.session_id)
            .join(Courses, Courses.id == Sessions.course_id)
            .filter(CheckIns.student_id == student.id, Sessions.course_id.in_(course_ids))
            .order_by(CheckIns.checked_in_at.desc())
            .limit(10)
            .all()
        ]

    total_sessions = sum(r["total_sessions"] for r in course_rows)
    attended_sessions = sum(r["sessions_attended"] for r in course_rows)
    return resp_student_stats(
        student_id=student.id,
        student_name=student.full_name,
        student_email=student.email,
        total_enrolled_courses=len(courses),
        total_sessions=total_sessions,
        attended_sessions=attended_sessions,
        attendance_rate=rate(attended_sessions, total_sessions),
        courses=course_rows,
        recent_sessions=recent,
        recent_checkins=recent,
    )
