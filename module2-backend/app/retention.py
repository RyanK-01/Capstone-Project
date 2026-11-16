import asyncio
import logging
import os
import secrets

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.database import LocalSession
from app.models import CheckIns, Devices, Risk_Signals, Users
from app.routers.security import get_password_hash
from app.utils import as_utc

# -----------------------------------------------------------------------------
# Data retention (retention.py)
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", 30))
RETENTION_INTERVAL_MINUTES = int(os.getenv("RETENTION_INTERVAL_MINUTES", 60))  # 0 turns the background job off
STARTUP_DELAY_SECONDS = 10
BATCH_SIZE = 500

ANONYMISED_EMAIL_DOMAIN = "deleted.invalid"

# Scheduling helpers (called by the endpoints that create check-ins or change a user's active state)
def deletion_date(start: datetime | None = None) -> datetime:
    return (start or datetime.now(timezone.utc)) + timedelta(days=RETENTION_DAYS)

def set_user_active(user: Users, active: bool) -> None:
    # Deactivating starts the clock; reactivating stops it
    user.is_active = active
    user.scheduled_deletion_at = None if active else (user.scheduled_deletion_at or deletion_date())

# Cleanup steps
def stamp_missing_dates(db: Session) -> int:
    # Rows created before retention existed have no date yet: derive it from when they were created or deactivated
    stamped = 0

    while True:
        rows = db.query(CheckIns).filter(CheckIns.scheduled_deletion_at.is_(None)).limit(BATCH_SIZE).all()
        if not rows:
            break
        for checkin in rows:
            checkin.scheduled_deletion_at = deletion_date(as_utc(checkin.checked_in_at))
        db.flush()
        stamped += len(rows)

    while True:
        rows = db.query(Users).filter(Users.is_active.is_(False), Users.scheduled_deletion_at.is_(None), ~Users.email.like(f"%@{ANONYMISED_EMAIL_DOMAIN}")).limit(BATCH_SIZE).all()
        if not rows:
            break
        for user in rows:
            user.scheduled_deletion_at = deletion_date(as_utc(user.updated_at))
        db.flush()
        stamped += len(rows)

    return stamped

def delete_expired_checkins(db: Session, now: datetime) -> int:
    deleted = 0

    while True:
        ids = [row[0] for row in db.query(CheckIns.id).filter(CheckIns.scheduled_deletion_at <= now).limit(BATCH_SIZE).all()]
        if not ids:
            break
        db.query(Risk_Signals).filter(Risk_Signals.checkin_id.in_(ids)).delete(synchronize_session=False)
        db.query(CheckIns).filter(CheckIns.id.in_(ids)).delete(synchronize_session=False)
        db.flush()
        deleted += len(ids)

    return deleted

def anonymise_user(db: Session, user: Users) -> None:
    user.full_name = "Deleted User"
    user.email = f"deleted-{user.id}@{ANONYMISED_EMAIL_DOMAIN}"
    user.hashed_password = get_password_hash(secrets.token_urlsafe(32))  # Unusable: nobody knows the password
    user.face_embedding_hash = None
    user.face_enrolled = False
    user.camera_consent = False
    user.geolocation_consent = False
    user.is_active = False
    user.scheduled_deletion_at = None  # Done; also keeps the user out of the next run

    # Devices stay (check-ins that are not expired yet point at them) but lose everything that identifies the person
    for device in db.query(Devices).filter(Devices.user_id == user.id).all():
        device.device_fingerprint = f"deleted-{device.id}"
        device.device_name = device.browser = device.os_version = device.app_version = device.attestation_token = None
        device.public_key = ""
        device.is_active = False

def anonymise_expired_users(db: Session, now: datetime) -> int:
    anonymised = 0

    while True:
        # Only deactivated accounts: reactivating one clears its date, so an active user is never touched
        users = db.query(Users).filter(Users.is_active.is_(False), Users.scheduled_deletion_at <= now).limit(BATCH_SIZE).all()
        if not users:
            break
        for user in users:
            anonymise_user(db, user)
        db.flush()
        anonymised += len(users)

    return anonymised

def run_retention(db: Session, now: datetime | None = None) -> dict[str, int]:
    # One full pass; safe to run repeatedly or from several workers at once
    now = now or datetime.now(timezone.utc)
    try:
        result = {
            "stamped": stamp_missing_dates(db),
            "checkins_deleted": delete_expired_checkins(db, now),
            "users_anonymised": anonymise_expired_users(db, now),
        }
        db.commit()
    except Exception:
        db.rollback()
        raise

    if result["checkins_deleted"] or result["users_anonymised"]:
        logger.info("Retention run: %s", result)
    return result

# Background job
def run_retention_once() -> dict[str, int] | None:
    # A failed run is logged and retried on the next interval; it must never take the API down
    db = LocalSession()
    try:
        return run_retention(db)
    except Exception:
        logger.exception("Retention run failed")
        return None
    finally:
        db.close()

async def retention_loop() -> None:
    # Start with asyncio.create_task(retention_loop()) when the app starts; the work runs in a thread, off the event loop
    if RETENTION_INTERVAL_MINUTES <= 0:
        logger.info("Retention job disabled (RETENTION_INTERVAL_MINUTES=%s)", RETENTION_INTERVAL_MINUTES)
        return

    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        await asyncio.to_thread(run_retention_once)
        await asyncio.sleep(RETENTION_INTERVAL_MINUTES * 60)
