import json
import math

from datetime import datetime, timezone
from fastapi import HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from typing import Generic, TypeVar

from app.models import Audit_Logs, Courses, Sessions, Users

# -----------------------------------------------------------------------------
# Shared helpers (utils.py)
# -----------------------------------------------------------------------------

# Audit helper
def write_audit(
    db: Session,
    request: Request,
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    success: bool = True,
    device_id: str | None = None,
) -> None:

    # Adds an audit entry to the session; the caller commits it with its own changes
    db.add(Audit_Logs(
        user_id = user_id,
        action = action,
        resource_type = resource_type,
        resource_id = resource_id,
        ip_address = request.client.host if request.client else None,
        user_agent = (request.headers.get("user-agent") or "")[:500] or None,
        device_id = device_id,
        details = json.dumps(details) if details is not None else None,
        success = success,
    ))

# Pagination response model
T = TypeVar("T")

class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

# Datetime helper
def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

# Course access helpers
def taught_by(user: Users, course_id_column):
    # SQL condition for "this user runs the course", usable in any query that exposes a course id column.
    # Courses have no instructor column, so the link is course -> session -> instructor.
    # An instructor can also reach a course that has no sessions yet (nobody runs it), so they can set it up.
    condition = course_id_column.in_(select(Sessions.course_id).where(Sessions.instructor_id == user.id))
    if user.role == "instructor":
        condition = or_(condition, course_id_column.not_in(select(Sessions.course_id)))
    return condition

def teaches_course(user: Users, course_id: str, db: Session) -> bool:
    if user.role == "admin":
        return True

    return db.query(Courses.id).filter(Courses.id == course_id, taught_by(user, Courses.id)).first() is not None

def require_course_access(user: Users, course_id: str, db: Session) -> None:
    if not teaches_course(user, course_id, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))
