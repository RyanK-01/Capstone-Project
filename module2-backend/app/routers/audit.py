import html
import json

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, status, HTTPException, Query
from pydantic import BaseModel, field_serializer
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Any

from app.database import get_db
from app.models import Audit_Logs, AuditAction, Users
from app.routers.security import require_role
from app.utils import Page, as_utc

# -----------------------------------------------------------------------------
# Audit Log Endpoints (audit.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/audit", tags=["audit"])

# Models
def escape_json(value: Any) -> Any:
    # Details can hold text copied from requests, so escape every string in it
    if isinstance(value, str):
        return html.escape(value)
    if isinstance(value, list):
        return [escape_json(v) for v in value]
    if isinstance(value, dict):
        return {k: escape_json(v) for k, v in value.items()}
    return value

class resp_audit_log(BaseModel):
    id: str
    user_id: str | None = None
    user_email: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    device_id: str | None = None
    details: Any = None
    success: bool | None = True
    timestamp: datetime

    # XSS Prevention
    @field_serializer("user_email", "user_agent")
    def escape_text(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

def action_value(value) -> str:
    return value.value if isinstance(value, AuditAction) else str(value)

def parse_details(text: str | None) -> Any:
    if not text:
        return None
    try:
        return escape_json(json.loads(text))
    except ValueError:
        return None

class resp_audit_summary(BaseModel):
    period_days: int
    total_logs: int
    failed_logs: int
    unique_users: int
    by_action: dict[str, int]

# GET /audit/summary - Audit log counts for the last N days (admin only)
@routers.get("/summary", response_model=resp_audit_summary, status_code=status.HTTP_200_OK)
def audit_summary(days: int = Query(default=7, ge=1, le=365), admin: Users = Depends(require_role("admin")), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    recent = Audit_Logs.timestamp >= since

    by_action = {action_value(action): count for action, count in db.query(Audit_Logs.action, func.count(Audit_Logs.id)).filter(recent).group_by(Audit_Logs.action).all()}
    failed = db.query(func.count(Audit_Logs.id)).filter(recent, Audit_Logs.success.is_(False)).scalar()
    users = db.query(func.count(func.distinct(Audit_Logs.user_id))).filter(recent).scalar()

    return resp_audit_summary(period_days=days, total_logs=sum(by_action.values()), failed_logs=failed or 0, unique_users=users or 0, by_action=by_action)

# GET /audit/ - Query audit logs (admin only)
@routers.get("/", response_model=Page[resp_audit_log], status_code=status.HTTP_200_OK)
def list_audit_logs(
    user_id: str | None = Query(default=None, max_length=36),
    action: str | None = Query(default=None, max_length=50),
    resource_type: str | None = Query(default=None, max_length=50),
    resource_id: str | None = Query(default=None, max_length=36),
    success: bool | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    admin: Users = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    query = db.query(Audit_Logs, Users.email).outerjoin(Users, Users.id == Audit_Logs.user_id)

    if user_id:
        query = query.filter(Audit_Logs.user_id == user_id)
    if action:
        try:
            query = query.filter(Audit_Logs.action == AuditAction(action))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown audit action")
    if resource_type:
        query = query.filter(Audit_Logs.resource_type == resource_type)
    if resource_id:
        query = query.filter(Audit_Logs.resource_id == resource_id)
    if success is not None:
        query = query.filter(Audit_Logs.success.is_(success))
    if start_date is not None:
        query = query.filter(Audit_Logs.timestamp >= as_utc(start_date))
    if end_date is not None:
        query = query.filter(Audit_Logs.timestamp <= as_utc(end_date))

    total = query.count()
    rows = query.order_by(Audit_Logs.timestamp.desc()).offset(offset).limit(limit).all()

    items = [
        resp_audit_log(
            id=log.id, user_id=log.user_id, user_email=email, action=action_value(log.action),
            resource_type=log.resource_type, resource_id=log.resource_id, ip_address=log.ip_address,
            user_agent=log.user_agent, device_id=log.device_id, details=parse_details(log.details),
            success=log.success, timestamp=log.timestamp,
        )
        for log, email in rows
    ]
    return Page[resp_audit_log](items=items, total=total, limit=limit, offset=offset)
