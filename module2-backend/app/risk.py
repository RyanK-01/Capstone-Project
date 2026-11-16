import json
import os

import httpx

from dataclasses import dataclass
from fastapi import Request
from sqlalchemy.orm import Session

from app.models import (
    AuditAction, CheckInStatus, Devices, Severity, SignalTypes, Sessions, Users,
)
from app.utils import haversine_meters

# -----------------------------------------------------------------------------
# Check-in risk assessment (risk.py)
# -----------------------------------------------------------------------------

FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://localhost:8001")
DEFAULT_RISK_THRESHOLD = 0.5
DEFAULT_GEOFENCE_METERS = 100.0
LOW_ACCURACY_METERS = 100.0

@dataclass
class Signal:
    type: SignalTypes
    severity: Severity
    weight: float
    details: dict | None = None

@dataclass
class Location:
    latitude: float | None = None
    longitude: float | None = None
    distance: float | None = None

@dataclass
class FaceResult:
    liveness_passed: bool | None = None
    liveness_score: float | None = None
    match_passed: bool | None = None
    match_score: float | None = None

@dataclass
class RiskAssessment:
    signals: list[Signal]
    risk_score: float
    status: CheckInStatus
    audit_action: AuditAction
    location: Location
    face: FaceResult
    device: Devices | None

    @property
    def risk_factors_json(self) -> str:
        return json.dumps([{"type": s.type.value, "severity": s.severity.value, "weight": s.weight, "details": s.details} for s in self.signals])

def call_face_service(path: str, payload: dict) -> dict | None:
    # The face service is optional: any failure is treated as "no result" instead of an error
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(f"{FACE_SERVICE_URL}{path}", json=payload)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError):
        return None

def location_signals(student: Users, session: Sessions, latitude: float, longitude: float, accuracy: float | None) -> tuple[Location, list[Signal]]:
    # The geofence is always checked, otherwise withdrawing consent would bypass it; coordinates are only stored with consent
    location, signals = Location(latitude, longitude), []
    if session.venue_latitude is not None and session.venue_longitude is not None:
        location.distance = round(haversine_meters(latitude, longitude, session.venue_latitude, session.venue_longitude), 2)
        geofence = session.geofence_radius_meters or DEFAULT_GEOFENCE_METERS
        if location.distance > geofence:
            critical = location.distance > 2 * geofence
            signals.append(Signal(SignalTypes.GEO_OUT_OF_BOUNDS, Severity.CRITICAL if critical else Severity.HIGH, 0.6 if critical else 0.4,
                                  {"distance_m": location.distance, "geofence_m": geofence}))
    if (accuracy or 0) > LOW_ACCURACY_METERS:
        signals.append(Signal(SignalTypes.GEO_ACCURACY_LOW, Severity.LOW, 0.1, {"accuracy_m": accuracy}))
    if not student.geolocation_consent:
        signals.append(Signal(SignalTypes.GEO_ACCURACY_LOW, Severity.MEDIUM, 0.2, {"reason": "no_geolocation_consent"}))
        return Location(), signals
    return location, signals

def device_signals(db: Session, student: Users, fingerprint: str | None) -> tuple[Devices | None, list[Signal]]:
    device = db.query(Devices).filter(Devices.device_fingerprint == fingerprint).first() if fingerprint else None
    if device is None:
        return None, [Signal(SignalTypes.DEVICE_UNKNOWN, Severity.MEDIUM, 0.15)]
    if device.user_id != student.id:
        return None, [Signal(SignalTypes.PATTERN_ANOMALY, Severity.HIGH, 0.3, {"reason": "device_registered_to_another_user"})]

    signals = []
    if not device.is_trusted:
        signals.append(Signal(SignalTypes.DEVICE_UNKNOWN, Severity.LOW, 0.05, {"reason": "device_not_trusted"}))
    if device.is_emulator:
        signals.append(Signal(SignalTypes.DEVICE_EMULATOR, Severity.HIGH, 0.3))
    if device.is_rooted_jailbroken:
        signals.append(Signal(SignalTypes.DEVICE_ROOTED, Severity.HIGH, 0.25))
    return device, signals

def face_signals(student: Users, session: Sessions, frames: list[str], challenge_type: str = "passive") -> tuple[FaceResult, list[Signal]]:
    result, signals = FaceResult(), []
    if not frames:
        if session.require_liveness_check:
            signals.append(Signal(SignalTypes.LIVENESS_LOW_CONFIDENCE, Severity.MEDIUM, 0.1, {"reason": "no_liveness_image"}))
        return result, signals

    image = frames[len(frames) // 2]
    payload = {"challenge_response": image, "challenge_type": challenge_type}
    if len(frames) > 1:
        payload["frames"] = frames
    live = call_face_service("/liveness/check", payload) or {}
    if live.get("liveness_passed") is not None:
        result.liveness_passed, result.liveness_score = bool(live["liveness_passed"]), live.get("liveness_score")
        if not result.liveness_passed:
            signals.append(Signal(SignalTypes.LIVENESS_FAILED, Severity.CRITICAL, 0.5, {"score": result.liveness_score, "challenge": challenge_type}))
    elif session.require_liveness_check:
        # Integration guide: when the face service gives no verdict, the check-in proceeds without liveness
        signals.append(Signal(SignalTypes.LIVENESS_LOW_CONFIDENCE, Severity.MEDIUM, 0.1, {"reason": "liveness_unavailable"}))

    # Match whenever the student has enrolled a face, not only when the session demands it
    if student.face_embedding_hash:
        match = call_face_service("/face/verify", {"image": image, "reference_template_hash": student.face_embedding_hash}) or {}
        if match.get("match_passed") is not None:
            result.match_passed, result.match_score = bool(match["match_passed"]), match.get("match_score")
            if not result.match_passed:
                signals.append(Signal(SignalTypes.FACE_MATCH_FAILED, Severity.HIGH, 0.4, {"score": result.match_score}))
        else:
            signals.append(Signal(SignalTypes.FACE_MATCH_LOW_CONFIDENCE, Severity.MEDIUM, 0.2, {"reason": "face_match_unavailable"}))
    elif session.require_face_match:
        signals.append(Signal(SignalTypes.FACE_MATCH_LOW_CONFIDENCE, Severity.MEDIUM, 0.2, {"reason": "student_not_enrolled"}))
    return result, signals

def decide(signals: list[Signal], threshold: float | None) -> tuple[float, CheckInStatus, AuditAction]:
    risk_score = round(min(1.0, sum(s.weight for s in signals)), 4)
    threshold = threshold if threshold is not None else DEFAULT_RISK_THRESHOLD
    if any(s.severity == Severity.CRITICAL for s in signals):
        return risk_score, CheckInStatus.REJECTED, AuditAction.CHECKIN_REJECTED
    if risk_score >= threshold or any(s.severity == Severity.HIGH for s in signals):
        return risk_score, CheckInStatus.FLAGGED, AuditAction.CHECKIN_FLAGGED
    return risk_score, CheckInStatus.APPROVED, AuditAction.CHECKIN_APPROVED

def assess_risk(db: Session, student: Users, session: Sessions, latitude: float, longitude: float, accuracy: float | None = None, device_fingerprint: str | None = None, frames: list[str] | None = None, request: Request | None = None, challenge_type: str = "passive") -> RiskAssessment:
    from app import antispoof

    location, signals = location_signals(student, session, latitude, longitude, accuracy)
    device, device_found = device_signals(db, student, device_fingerprint)
    frames = frames or []
    face, face_found = face_signals(student, session, frames, challenge_type)
    signals += device_found + face_found

    # Anti-spoofing: GPS spoofing, replayed liveness images and VPN/proxy/Tor
    signals += antispoof.gps_signals(db, student, session, latitude, longitude, accuracy) + antispoof.replay_signals(frames)
    if request is not None:
        signals += antispoof.network_signals(request)

    risk_score, status, audit_action = decide(signals, session.risk_threshold)
    return RiskAssessment(signals=signals, risk_score=risk_score, status=status, audit_action=audit_action, location=location, face=face, device=device)
