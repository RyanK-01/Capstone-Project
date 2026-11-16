import html

from datetime import datetime
from fastapi import APIRouter, Depends, status, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Literal

from app.database import get_db
from app.models import AuditAction, Devices, Users
from app.routers.security import get_current_user, require_role
from app.utils import Page, write_audit

# -----------------------------------------------------------------------------
# Device Endpoints (devices.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/devices", tags=["devices"])

# Models
class register_device(BaseModel):
    device_fingerprint: str = Field(min_length=1, max_length=64, pattern=r"^[\w.\-:]+$")
    device_name: str | None = Field(default=None, max_length=255)
    platform: Literal["ios", "android", "web", "desktop"] | None = None
    browser: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=50)
    app_version: str | None = Field(default=None, max_length=50)
    public_key: str | None = Field(default=None, max_length=4096)

class update_device(BaseModel):
    device_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_trusted: bool | None = None
    is_active: bool | None = None

class resp_device(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    device_fingerprint: str
    device_name: str | None = None
    platform: str | None = None
    is_trusted: bool | None = False
    trust_score: str | None = "low"
    is_active: bool
    first_seen_at: datetime
    last_seen_at: datetime | None = None
    total_checkins: int | None = 0

    # XSS Prevention
    @field_serializer("device_name")
    def escape_name(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

class resp_device_admin(resp_device):
    user_id: str
    user_email: str | None = None

    # XSS Prevention
    @field_serializer("user_email")
    def escape_email(self, value: str | None) -> str | None:
        return html.escape(value) if value is not None else None

def get_device_or_404(device_id: str, user: Users, db: Session) -> Devices:
    device = db.query(Devices).filter(Devices.id == device_id).first()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if device.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return device

# POST /devices/register - Register device
@routers.post("/register", response_model=resp_device, status_code=status.HTTP_201_CREATED)
def register(body: register_device, request: Request, response: Response, user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(Devices).filter(Devices.device_fingerprint == body.device_fingerprint).first()
    if existing is not None:
        # A fingerprint belongs to one user; registering it again as the owner is harmless
        if existing.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Device already registered")
        if not existing.is_active:
            existing.is_active = True
            db.commit()
            db.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return existing

    device = Devices(
        user_id=user.id,
        device_fingerprint=body.device_fingerprint,
        device_name=body.device_name,
        platform=body.platform,
        browser=body.browser,
        os_version=body.os_version,
        app_version=body.app_version,
        public_key=body.public_key or "",
    )
    db.add(device)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Device already registered")

    write_audit(db, request, user.id, AuditAction.DEVICE_REGISTERED, "device", device.id, {"platform": body.platform})
    db.commit()
    db.refresh(device)

    return device

# GET /devices/ - List all devices (admin only)
@routers.get("/", response_model=Page[resp_device_admin], status_code=status.HTTP_200_OK)
def list_devices(
    user_id: str | None = Query(default=None, max_length=36),
    is_trusted: bool | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: Users = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    query = db.query(Devices, Users.email).join(Users, Users.id == Devices.user_id)
    if user_id:
        query = query.filter(Devices.user_id == user_id)
    if is_trusted is not None:
        query = query.filter(Devices.is_trusted.is_(is_trusted))
    if is_active is not None:
        query = query.filter(Devices.is_active.is_(is_active))

    total = query.count()
    rows = query.order_by(Devices.first_seen_at.desc()).offset(offset).limit(limit).all()

    items = [resp_device_admin.model_validate(device).model_copy(update={"user_email": email}) for device, email in rows]
    return Page[resp_device_admin](items=items, total=total, limit=limit, offset=offset)

# GET /devices/my-devices - Current user's devices
@routers.get("/my-devices", response_model=list[resp_device], status_code=status.HTTP_200_OK)
def my_devices(include_inactive: bool = Query(default=False), user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Devices).filter(Devices.user_id == user.id)
    if not include_inactive:
        query = query.filter(Devices.is_active.is_(True))

    return query.order_by(Devices.first_seen_at.desc()).all()

# PATCH /devices/{device_id} - Update device
@routers.patch("/{device_id}", response_model=resp_device, status_code=status.HTTP_200_OK)
def edit_device(device_id: str, body: update_device, user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    device = get_device_or_404(device_id, user, db)
    data = body.model_dump(exclude_unset=True)

    # Only an admin can change the trust level
    if data.get("is_trusted") is not None and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if data.get("device_name") is not None:
        device.device_name = data["device_name"]
    if data.get("is_active") is not None:
        device.is_active = data["is_active"]
    if data.get("is_trusted") is not None:
        device.is_trusted = data["is_trusted"]
        device.trust_score = "high" if data["is_trusted"] else "low"

    db.commit()
    db.refresh(device)

    return device

# DELETE /devices/{device_id} - Remove device
@routers.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_device(device_id: str, user: Users = Depends(get_current_user), db: Session = Depends(get_db)):
    device = get_device_or_404(device_id, user, db)

    # Deactivated, not deleted, so past check-ins keep their device record
    device.is_active = False
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
