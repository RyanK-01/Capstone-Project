"""
SAIV Backend API - Module 2

This is the skeleton implementation for the Backend API module.
Students must implement all endpoints according to the API specification.

See: docs/API-SPECIFICATION.md for complete endpoint documentation.
"""
import asyncio
import os

from contextlib import asynccontextmanager, suppress
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.database import Base, engine
from app.metrics import MetricsMiddleware, metrics_router
from app.middleware import SecurityHeadersMiddleware
from app.retention import retention_loop
from app.telemetry import setup_telemetry
from app import models
from app.routers import admin, audit, auth, checkins, courses, sessions, users, stats, export, enrollments, devices

Base.metadata.create_all(bind=engine)

# Audit logs are append-only: the database itself refuses UPDATE and DELETE
if engine.dialect.name == "postgresql":
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE OR REPLACE FUNCTION audit_logs_append_only() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_logs is append-only';
            END;
            $$ LANGUAGE plpgsql
        """))
        connection.execute(text("DROP TRIGGER IF EXISTS audit_logs_no_change ON audit_logs"))
        connection.execute(text("""
            CREATE TRIGGER audit_logs_no_change BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only()
        """))

# Data retention job (30-day cleanup of check-ins and deactivated users) runs in the background while the API is up
@asynccontextmanager
async def lifespan(app: FastAPI):
    retention_task = asyncio.create_task(retention_loop())
    yield
    retention_task.cancel()
    with suppress(asyncio.CancelledError):
        await retention_task

app = FastAPI(
    title="SAIV Backend API",
    description="Secure Attendance & Identity Verification System",
    version="1.0.0",
    lifespan=lifespan,
)

# Unhandled errors answer with the JSON body from the API specification instead of plain text
@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# CORS middleware - econfigure appropriately for your frontend
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8501").split(",") if o.strip() and o.strip() != "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Security headers on every response (added last so it also covers CORS preflight responses)
app.add_middleware(SecurityHeadersMiddleware)

# Request timing for Prometheus (outermost, so it times the whole stack) and the /metrics endpoint it is scraped from
app.add_middleware(MetricsMiddleware)
app.include_router(metrics_router)


setup_telemetry(app, engine)

@app.get("/health")
def health_check():
    """Health check endpoint: 200 when the API and its database respond, 503 otherwise."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "service": "backend"})
    return {"status": "healthy", "service": "backend"}

api_v1 = APIRouter(prefix="/api/v1")

# =============================================================================
# TODO: Implement the following endpoints
# =============================================================================
# All paths are relative to the /api/v1 prefix (GET /users/me is served at
# GET /api/v1/users/me). This list mirrors docs/API-SPECIFICATION.md; if the
# two ever disagree, the specification (and tests/public/) is authoritative.

# -----------------------------------------------------------------------------
# Authentication Endpoints (auth.py)
# -----------------------------------------------------------------------------
# POST /auth/register - User registration
# POST /auth/login - JWT token generation
# POST /auth/refresh - Token refresh
api_v1.include_router(auth.routers)

# -----------------------------------------------------------------------------
# User Management Endpoints (users.py)
# -----------------------------------------------------------------------------
# GET /users/me - Current user info
# PUT /users/me - Update profile / consent flags
# POST /users/me/face/enroll - Enroll face (proxies to the face service)
# GET /users/ - List users (admin only)
# GET /users/{user_id} - User details (admin only)
# PATCH /users/{user_id} - Update user (admin only)
api_v1.include_router(users.routers)

# -----------------------------------------------------------------------------
# Course Management Endpoints (courses.py)
# -----------------------------------------------------------------------------
# GET /courses/ - List courses
# GET /courses/{course_id} - Course details
# POST /courses/ - Create course (admin only)
# PUT /courses/{course_id} - Update course (admin only)
# DELETE /courses/{course_id} - Soft-delete course (admin only)
api_v1.include_router(courses.routers)

# -----------------------------------------------------------------------------
# Session Management Endpoints (sessions.py)
# -----------------------------------------------------------------------------
# GET /sessions/ - List sessions (instructor/admin)
# GET /sessions/active - Currently open sessions (public, no auth)
# GET /sessions/my-sessions - Sessions relevant to the current user
# GET /sessions/{session_id} - Session details
# POST /sessions/ - Create session (instructor)
# PATCH /sessions/{session_id} - Update session
# DELETE /sessions/{session_id} - Delete session
api_v1.include_router(sessions.routers)

# -----------------------------------------------------------------------------
# Check-in Endpoints (checkins.py)
# -----------------------------------------------------------------------------
# POST /checkins/ - Submit check-in
# GET /checkins/ - List check-ins (with filters)
# GET /checkins/my-checkins - Student's own check-ins
# GET /checkins/session/{session_id} - Check-ins for a session
# GET /checkins/flagged - Flagged check-ins
# GET /checkins/{checkin_id} - Check-in details
# POST /checkins/{checkin_id}/appeal - Student appeals a check-in
# POST /checkins/{checkin_id}/review - Instructor reviews an appeal
api_v1.include_router(checkins.routers)

# -----------------------------------------------------------------------------
# Statistics Endpoints (stats.py)
# -----------------------------------------------------------------------------
# GET /stats/overview - System overview
# GET /stats/sessions/{session_id} - Session statistics
# GET /stats/courses/{course_id} - Course statistics
# GET /stats/students/{student_id} - Student statistics
api_v1.include_router(stats.routers)

# -----------------------------------------------------------------------------
# Device Endpoints (devices.py)
# -----------------------------------------------------------------------------
# POST /devices/register - Register device
# GET /devices/my-devices - Current user's devices
# PATCH /devices/{device_id} - Update device
# DELETE /devices/{device_id} - Remove device
api_v1.include_router(devices.routers)

# -----------------------------------------------------------------------------
# Enrollment Endpoints (enrollments.py)
# -----------------------------------------------------------------------------
# GET /enrollments/my-enrollments - Student's enrollments
# GET /enrollments/course/{course_id} - Students enrolled in a course
# POST /enrollments/ - Enroll a student
# POST /enrollments/bulk - Bulk enroll
# DELETE /enrollments/{enrollment_id} - Drop enrollment
api_v1.include_router(enrollments.routers)

# -----------------------------------------------------------------------------
# Audit Log Endpoints (audit.py)
# -----------------------------------------------------------------------------
# GET /audit/ - Query audit logs (admin only)
# Audit logs are append-only: there is no create/update/delete endpoint.
# Entries are written internally by the other endpoints.
api_v1.include_router(audit.routers)

# -----------------------------------------------------------------------------
# Export Endpoints (export.py)
# -----------------------------------------------------------------------------
# GET /export/attendance/{course_id} - CSV attendance export for a course
# GET /export/session/{session_id} - CSV export for a session
api_v1.include_router(export.routers)

# -----------------------------------------------------------------------------
# Admin Endpoints (admin.py) - Required for automated testing
# -----------------------------------------------------------------------------
# PATCH /admin/users/{user_id}/deactivate - Deactivate user (admin only)
# PATCH /admin/users/{user_id}/activate - Activate user (admin only)
# POST /admin/users/bulk - Bulk create users (admin only)
# PATCH /admin/sessions/{session_id}/status - Update session status (admin only)
# POST /admin/enrollments/ - Admin enrollment creation (admin only)
api_v1.include_router(admin.routers)

# =============================================================================
# Database Models to Implement (see DATABASE-SCHEMA.md)
# =============================================================================
# - users
# - courses
# - enrollments
# - sessions
# - checkins
# - devices
# - risksignals
# - auditlogs

# =============================================================================
# Security Requirements
# =============================================================================
# - JWT authentication with HS256
# - Bcrypt password hashing (cost >= 10)
# - Role-based access control (student, instructor, ta, admin)
# - Input validation and sanitization
# - Rate limiting
# - CORS configuration
app.include_router(api_v1)