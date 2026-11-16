import base64
import hashlib
import os
import uuid
import enum
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

from sqlalchemy.types import TypeDecorator
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Enum,
    DateTime,
    Index,
    Text,
    Float,
    ForeignKey,
    CheckConstraint,
)

from app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

# ENCRYPTION_KEY is a Fernet key; without it one is derived from SECRET_KEY so no new setting is required
_fernet = Fernet(os.getenv("ENCRYPTION_KEY") or base64.urlsafe_b64encode(hashlib.sha256((os.getenv("SECRET_KEY") or "").encode()).digest()))

# Stored encrypted, read back as plain text
class EncryptedText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return _fernet.encrypt(value.encode()).decode() if value else value

    def process_result_value(self, value, dialect):
        if not value:
            return value
        try:
            return _fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            return value

class UserRole(str, enum.Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    TA = "ta"
    ADMIN = "admin"

class SessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    
class CheckInStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    FLAGGED = "flagged"
    REJECTED = "rejected"
    APPEALED = "appealed"
    
class SignalTypes(str, enum.Enum):
    GEO_OUT_OF_BOUNDS = "geo_out_of_bounds"
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    GEO_ACCURACY_LOW = "geo_accuracy_low"

    VPN_DETECTED = "vpn_detected"
    PROXY_DETECTED = "proxy_detected"
    TOR_DETECTED = "tor_detected"
    SUSPICIOUS_IP = "suspicious_ip"

    DEVICE_UNKNOWN = "device_unknown"
    DEVICE_EMULATOR = "device_emulator"
    DEVICE_ROOTED = "device_rooted"
    ATTESTATION_FAILED = "attestation_failed"

    RAPID_SUCCESSION = "rapid_succession"
    UNUSUAL_TIME = "unusual_time"
    PATTERN_ANOMALY = "pattern_anomaly"

    LIVENESS_FAILED = "liveness_failed"
    LIVENESS_LOW_CONFIDENCE = "liveness_low_confidence"
    DEEPFAKE_SUSPECTED = "deepfake_suspected"
    REPLAY_SUSPECTED = "replay_suspected"

    FACE_MATCH_FAILED = "face_match_failed"
    FACE_MATCH_LOW_CONFIDENCE = "face_match_low_confidence"

class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AuditAction(str, enum.Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    CHECKIN_ATTEMPTED = "checkin_attempted"
    CHECKIN_APPROVED = "checkin_approved"
    CHECKIN_FLAGGED = "checkin_flagged"
    CHECKIN_REJECTED = "checkin_rejected"
    CHECKIN_APPEALED = "checkin_appealed"
    CHECKIN_REVIEWED = "checkin_reviewed"
    SESSION_CREATED = "session_created"
    SESSION_UPDATED = "session_updated"
    SESSION_DELETED = "session_deleted"
    ENROLLMENT_ADDED = "enrollment_added"
    ENROLLMENT_REMOVED = "enrollment_removed"
    DEVICE_REGISTERED = "device_registered"
    FACE_ENROLLED = "face_enrolled"
    DATA_EXPORTED = "data_exported"
    SECURITY_VIOLATION = "security_violation"

class Users(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    camera_consent = Column(Boolean, default=False)
    geolocation_consent = Column(Boolean, default=False)
    face_embedding_hash = Column(String(64), nullable=True)
    face_enrolled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_deletion_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_users_role_is_active", "role", "is_active"),)

    def __repr__(self) -> str:
        return f"<Users id={self.id}, email={self.email}, role={self.role}>"

class Courses(Base):
    __tablename__ = "courses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    semester = Column(String(20), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    venue_latitude = Column(Float, nullable=True)
    venue_longitude = Column(Float, nullable=True)
    venue_name = Column(String(255), nullable=True)
    geofence_radius_meters = Column(Float, default=100.0)
    require_face_recognition = Column(Boolean, default=False)
    require_device_binding = Column(Boolean, default=True)
    risk_threshold = Column(Float, default=0.5)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("risk_threshold >= 0 AND risk_threshold <= 1", name="risk_threshold_range"),
    )

    def __repr__(self) -> str:
        return f"<Courses id={self.id}, code={self.code}, semester={self.semester}, is_active={self.is_active}>"

class Enrollments(Base):
    __tablename__ = "enrollments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String(36), ForeignKey("courses.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    enrolled_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    dropped_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_enrollments_student_id_course_id", "student_id", "course_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Enrollments id={self.id}, student_id={self.student_id}, course_id={self.course_id}, is_active={self.is_active}>"

class Sessions(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    course_id = Column(String(36), ForeignKey("courses.id"), nullable=False, index=True)
    instructor_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    session_type = Column(String(50), default="lecture")
    description = Column(Text, nullable=True)
    scheduled_start = Column(DateTime(timezone=True), nullable=False, index=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=False)
    checkin_opens_at = Column(DateTime(timezone=True), nullable=False)
    checkin_closes_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(SessionStatus, name="session_status", values_callable=lambda e: [m.value for m in e]), nullable=False, index=True)
    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)
    venue_latitude = Column(Float, nullable=True)
    venue_longitude = Column(Float, nullable=True)
    venue_name = Column(String(255), nullable=True)
    geofence_radius_meters = Column(Float, nullable=True)
    require_liveness_check = Column(Boolean, default=True)
    require_face_match = Column(Boolean, default=False)
    risk_threshold = Column(Float, nullable=True)
    qr_code_secret = Column(String(64), nullable=True)
    qr_code_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_sessions_checkin_opens_at_checkin_closes_at", "checkin_opens_at", "checkin_closes_at"),
        CheckConstraint("scheduled_start < scheduled_end", name="scheduled_window"),
        CheckConstraint("checkin_opens_at < checkin_closes_at", name="checkin_window"),
        CheckConstraint("actual_start < actual_end", name="actual_window"),
    )

    def __repr__(self) -> str:
        return f"<Sessions id={self.id}, course_id={self.course_id}, name={self.name}, status={self.status}>"

class Devices(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    device_fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    device_name = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=True)
    browser = Column(String(100), nullable=True)
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(50), nullable=True)
    public_key = Column(EncryptedText, nullable=False)
    public_key_created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    public_key_expires_at = Column(DateTime(timezone=True), nullable=True)
    attestation_passed = Column(Boolean, default=False)
    last_attestation_at = Column(DateTime(timezone=True), nullable=True)
    attestation_token = Column(EncryptedText, nullable=True)
    is_trusted = Column(Boolean, default=False, index=True)
    trust_score = Column(String(20), default="low")
    is_emulator = Column(Boolean, default=False)
    is_rooted_jailbroken = Column(Boolean, default=False)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    total_checkins = Column(Integer, default=0)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Devices id={self.id}, user_id={self.user_id}, device_fingerprint={self.device_fingerprint}, is_trusted={self.is_trusted}, is_active={self.is_active}>"

class CheckIns(Base):
    __tablename__ = "checkins"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    status = Column(Enum(CheckInStatus, name="checkin_status", values_callable=lambda e: [m.value for m in e]), nullable=False, index=True)
    checked_in_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_accuracy_meters = Column(Float, nullable=True)
    distance_from_venue_meters = Column(Float, nullable=True)
    liveness_passed = Column(Boolean, nullable=True)
    liveness_score = Column(Float, nullable=True)
    liveness_challenge_type = Column(String(50), nullable=True)
    face_match_passed = Column(Boolean, nullable=True)
    face_match_score = Column(Float, nullable=True)
    face_embedding_hash = Column(String(64), nullable=True)
    risk_score = Column(Float, nullable=False, default=0.0, index=True)
    risk_factors = Column(Text, nullable=True)
    qr_code_verified = Column(Boolean, default=False)
    reviewed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    appeal_reason = Column(Text, nullable=True)
    appealed_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_deletion_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_checkins_session_id_student_id", "session_id", "student_id", unique=True),
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="risk_score_range"),
        CheckConstraint("liveness_score >= 0 AND liveness_score <= 1", name="liveness_score_range"),
        CheckConstraint("face_match_score >= 0 AND face_match_score <= 1", name="face_match_score_range"),
    )

    def __repr__(self) -> str:
        return f"<CheckIns id={self.id}, session_id={self.session_id}, student_id={self.student_id}, status={self.status}, risk_score={self.risk_score}>"

class Risk_Signals(Base):
    __tablename__ = "risk_signals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    checkin_id = Column(String(36), ForeignKey("checkins.id"), nullable=False, index=True)
    signal_type = Column(Enum(SignalTypes, name="signal_type", values_callable=lambda e: [m.value for m in e]), nullable=False, index=True)
    severity = Column(Enum(Severity, name="severity", values_callable=lambda e: [m.value for m in e]), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=1.0)
    details = Column(Text, nullable=True)
    weight = Column(Float, nullable=False, default=0.1)
    detected_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("weight >= 0", name="weight_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<Risk_Signals id={self.id}, checkin_id={self.checkin_id}, signal_type={self.signal_type}, severity={self.severity}>"

class Audit_Logs(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(Enum(AuditAction, name="audit_action", values_callable=lambda e: [m.value for m in e]), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    device_id = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_audit_logs_resource_type_resource_id", "resource_type", "resource_id"),
    )

    def __repr__(self) -> str:
        return f"<Audit_Logs id={self.id}, user_id={self.user_id}, action={self.action}, success={self.success}, timestamp={self.timestamp}>"
