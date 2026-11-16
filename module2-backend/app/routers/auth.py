import os

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, status, HTTPException
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Literal
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.geo import client_ip
from app.models import AuditAction, Audit_Logs, Users
from app.ratelimit import HOUR, LOGIN_PER_HOUR, REGISTER_PER_HOUR, enforce
from app.routers.security import (get_password_hash, verify_password, create_access_token, create_refresh_token, get_user_from_token)
from app.utils import as_utc, write_audit

# -----------------------------------------------------------------------------
# Authentication Endpoints (auth.py)
# -----------------------------------------------------------------------------

# Routers for main.py
routers = APIRouter(prefix="/auth", tags=["auth"])

# Account lockout: after LOCKOUT_ATTEMPTS consecutive failed passwords the account answers 429 for LOCKOUT_MINUTES.
# State is read from the audit log (failures since the last successful login), so it needs no extra column or Redis.
LOCKOUT_ATTEMPTS = int(os.getenv("LOGIN_LOCKOUT_ATTEMPTS", 10))
LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", 15))

def lockout_seconds_left(user: Users, db: Session) -> int:
    now = datetime.now(timezone.utc)
    window = timedelta(minutes=LOCKOUT_MINUTES)

    # Only failures after the last successful login, and inside the lockout window, count
    since = now - window
    last_success = db.query(func.max(Audit_Logs.timestamp)).filter(
        Audit_Logs.user_id == user.id, Audit_Logs.action == AuditAction.LOGIN_SUCCESS
    ).scalar()
    if last_success is not None:
        since = max(since, as_utc(last_success))

    failures = [
        as_utc(row[0]) for row in db.query(Audit_Logs.timestamp)
        .filter(
            Audit_Logs.user_id == user.id,
            Audit_Logs.action == AuditAction.LOGIN_FAILED,
            Audit_Logs.details.like("%invalid_credentials%"),
            Audit_Logs.timestamp > since,
        )
        .order_by(Audit_Logs.timestamp)
        .all()
    ]
    if len(failures) < LOCKOUT_ATTEMPTS:
        return 0

    # The lock lifts when the oldest of the last LOCKOUT_ATTEMPTS failures leaves the window
    unlock_at = failures[-LOCKOUT_ATTEMPTS] + window
    return max(0, int((unlock_at - now).total_seconds()) + 1)

# Models
class req_account(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8) 
    full_name: str = Field(min_length=1)
    role: Literal["student", "instructor", "ta", "admin"] = "student"

class resp_account(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

class login_account(BaseModel):
    email: EmailStr
    password: str

class token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
   
class login_token(token):
    user: resp_account
    
class refresh_request(BaseModel):
    refresh_token: str

# POST /auth/register - User registration
@routers.post("/register", response_model = resp_account,status_code=status.HTTP_201_CREATED)
def register_acc(acc: req_account, request: Request, db: Session = Depends(get_db)):
    enforce("register", client_ip(request), REGISTER_PER_HOUR, HOUR)

    existing = db.query(Users).filter(Users.email == acc.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    new_user = Users(
        email = acc.email,
        full_name = acc.full_name,
        hashed_password = get_password_hash(acc.password),
        role = acc.role
    )
    
    db.add(new_user)
    try:
        db.flush()
        write_audit(db, request, new_user.id, AuditAction.USER_CREATED, "user", new_user.id, {"role": acc.role})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    db.refresh(new_user)
    
    return new_user

# POST /auth/login - JWT token generation
@routers.post("/login", response_model=login_token, status_code=status.HTTP_200_OK)
def login(acc: login_account, request: Request, db: Session = Depends(get_db)):
    enforce("login", client_ip(request), LOGIN_PER_HOUR, HOUR)

    user = db.query(Users).filter(Users.email == acc.email).first()

    # A locked account answers 429 whatever the password is, so the lock cannot be tested for free
    if user:
        retry_after = lockout_seconds_left(user, db)
        if retry_after:
            write_audit(db, request, user.id, AuditAction.SECURITY_VIOLATION, "user", user.id, {"email": acc.email, "reason": "account_locked"}, success=False)
            db.commit()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed login attempts. Try again later.", headers={"Retry-After": str(retry_after)})

    if not user or not verify_password(acc.password, user.hashed_password):
        write_audit(db, request, user.id if user else None, AuditAction.LOGIN_FAILED, "user", user.id if user else None, {"email": acc.email, "reason": "invalid_credentials"}, success=False)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
    
    if not user.is_active:
        write_audit(db, request, user.id, AuditAction.LOGIN_FAILED, "user", user.id, {"email": acc.email, "reason": "account_disabled"}, success=False)
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    
    user.last_login_at = datetime.now(timezone.utc)
    write_audit(db, request, user.id, AuditAction.LOGIN_SUCCESS, "user", user.id)
    db.commit()
    db.refresh(user)
    
    return login_token(access_token=create_access_token(user), refresh_token=create_refresh_token(user), user=user)

# POST /auth/refresh - Token refresh
@routers.post("/refresh", response_model=token, status_code=status.HTTP_200_OK)
def refresh(body: refresh_request, db: Session = Depends(get_db)):
    user = get_user_from_token(body.refresh_token, db, expected_type="refresh")
    return token(access_token=create_access_token(user), refresh_token=create_refresh_token(user))
