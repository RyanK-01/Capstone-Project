import csv
import html
import io
import re

from datetime import datetime
from fastapi import APIRouter, Depends, status, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.models import AuditAction, CheckIns, CheckInStatus, Courses, Enrollments, SessionStatus, Sessions, Users
from app.routers.security import require_role
from app.utils import as_utc, require_course_access, write_audit

# -----------------------------------------------------------------------------
# Export Endpoints (export.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/export", tags=["export"])

CSV_COLUMNS = ["student_id", "student_name", "student_email", "session_date", "session_name", "status", "checked_in_at", "risk_score"]
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# CSV injection guard
def csv_safe(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text

def status_name(value) -> str:
    return value.value if hasattr(value, "value") else str(value)

def iso(value: datetime | None) -> str:
    return as_utc(value).isoformat() if value is not None else ""

def build_records(sessions: list[Sessions], students: list[Users], checkins: dict[tuple[str, str], CheckIns]) -> list[dict]:
    # One row per enrolled student per session; students without a check-in are absent
    records = []
    for session in sessions:
        for student in students:
            checkin = checkins.get((session.id, student.id))
            records.append({
                "student_id": student.id,
                "student_name": student.full_name,
                "student_email": student.email,
                "session_date": as_utc(session.scheduled_start).date().isoformat(),
                "session_name": session.name,
                "status": status_name(checkin.status) if checkin else "absent",
                "checked_in_at": iso(checkin.checked_in_at) if checkin else "",
                "risk_score": checkin.risk_score if checkin else "",
            })
    return records

def csv_response(records: list[dict], filename: str) -> Response:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for record in records:
        writer.writerow({column: csv_safe(record[column]) for column in CSV_COLUMNS})

    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )

# XSS Prevention for the JSON format
def escape_records(records: list[dict]) -> list[dict]:
    text_columns = ("student_name", "student_email", "session_name")
    return [{k: (html.escape(v) if k in text_columns else v) for k, v in record.items()} for record in records]

def attended_count(records: list[dict]) -> int:
    return sum(1 for r in records if r["status"] not in ("absent", "rejected"))

def load_enrolled(course_id: str, db: Session) -> list[Users]:
    return (
        db.query(Users)
        .join(Enrollments, Enrollments.student_id == Users.id)
        .filter(Enrollments.course_id == course_id, Enrollments.is_active.is_(True))
        .order_by(Users.full_name)
        .all()
    )

def load_checkins(session_ids: list[str], db: Session) -> dict[tuple[str, str], CheckIns]:
    if not session_ids:
        return {}
    rows = db.query(CheckIns).filter(CheckIns.session_id.in_(session_ids)).all()
    return {(c.session_id, c.student_id): c for c in rows}

# GET /export/attendance/{course_id} - CSV attendance export for a course
@routers.get("/attendance/{course_id}", status_code=status.HTTP_200_OK)
def export_attendance(
    course_id: str,
    request: Request,
    format: Literal["csv", "json"] = Query(default="csv"),
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

    students = load_enrolled(course.id, db)
    records = build_records(sessions, students, load_checkins([s.id for s in sessions], db))

    write_audit(db, request, user.id, AuditAction.DATA_EXPORTED, "course", course.id, {"export_type": "attendance", "format": format, "rows": len(records)})
    db.commit()

    if format == "csv":
        return csv_response(records, f"attendance_{course.code}.csv")

    return {
        "course_id": course.id,
        "course_code": html.escape(course.code),
        "summary": {
            "total_enrolled": len(students),
            "total_sessions": len(sessions),
            "attendance_rate": round(attended_count(records) / len(records), 4) if records else 0.0,
        },
        "records": escape_records(records),
    }

# GET /export/session/{session_id} - CSV export for a session
@routers.get("/session/{session_id}", status_code=status.HTTP_200_OK)
def export_session(
    session_id: str,
    request: Request,
    format: Literal["csv", "json"] = Query(default="csv"),
    user: Users = Depends(require_role("admin", "instructor")),
    db: Session = Depends(get_db),
):
    session = db.query(Sessions).filter(Sessions.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    require_course_access(user, session.course_id, db)

    students = load_enrolled(session.course_id, db)
    records = build_records([session], students, load_checkins([session.id], db))

    write_audit(db, request, user.id, AuditAction.DATA_EXPORTED, "session", session.id, {"export_type": "session", "format": format, "rows": len(records)})
    db.commit()

    if format == "csv":
        return csv_response(records, f"session_{session.id}.csv")

    counts = {s.value: 0 for s in CheckInStatus}
    for record in records:
        if record["status"] in counts:
            counts[record["status"]] += 1
    return {
        "session_id": session.id,
        "session_name": html.escape(session.name),
        "summary": {
            "total_enrolled": len(students),
            "checked_in": attended_count(records),
            "attendance_rate": round(attended_count(records) / len(students), 4) if students else 0.0,
            "by_status": counts,
        },
        "records": escape_records(records),
    }
