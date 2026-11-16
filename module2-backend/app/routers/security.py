import os

from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Users
from app.ratelimit import API_PER_HOUR, HOUR, enforce

# =============================================================================
# Security Requirements
# =============================================================================
# - JWT authentication with HS256
# - Bcrypt password hashing (cost >= 10)
# - Role-based access control (student, instructor, ta, admin)
# - Input validation and sanitization
# - Rate limiting
# - CORS configuration

#Configurations
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Copy .env.example to .env and export it, "
        "or run the stack with docker compose."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))
bearer_scheme = HTTPBearer(auto_error=False)

#Encrypting and Validating password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=max(10, int(os.getenv("BCRYPT_ROUNDS", 10))))

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hash_password: str) -> bool:
    return pwd_context.verify(plain_password, hash_password)

#Token creation
def create_token(user:Users, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "type": token_type,
        "exp": now + expires_delta,
        "iat": now
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_access_token(user: Users) -> str:
    return create_token(user, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), "access")

def create_refresh_token(user: Users) -> str:
    return create_token(user, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS), "refresh")

#Token Validation
credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception
    
    if not payload.get("sub"):
        raise credentials_exception
    
    return payload

def get_user_from_token(token: str, db: Session, expected_type: str = "access") -> Users:
    payload = decode_token(token)
    if payload.get("type") != expected_type:
        raise credentials_exception
    user = db.query(Users).filter(Users.id == payload["sub"]).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user

#Dependencies
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)) -> Users:
    if credentials is None:
        raise credentials_exception
    
    user = get_user_from_token(credentials.credentials, db)
    enforce("api", user.id, API_PER_HOUR, HOUR)
    return user

def require_role(*role: str):
    def dependency(user: Users = Depends(get_current_user)) -> Users:
        if user.role not in role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency