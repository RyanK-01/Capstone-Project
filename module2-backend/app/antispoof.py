import hashlib
import ipaddress
import re
import time

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import redis

from fastapi import Request
from sqlalchemy.orm import Session

from app.geo import client_ip, parse_ip
from app.models import CheckIns, Severity, SignalTypes, Sessions, Users
from app.ratelimit import get_client
from app.risk import Signal
from app.utils import as_utc, haversine_meters

# GPS
MAX_SPEED_MPS = 70                  # ~250 km/h, faster than any student can move between two check-ins
MIN_TRAVEL_METERS = 1000            # Shorter hops are GPS noise, not travel
MIN_PLAUSIBLE_ACCURACY_METERS = 1   # A phone never reports a fix this precise, mock-location apps do
CLUSTER_DEGREES = 1e-5              # ~1 m: identical coordinates for different students
CLUSTER_STUDENTS = 2                # Other students on the exact same spot before it looks scripted

# Replay
IMAGE_TTL_SECONDS = 24 * 3600

# Network
VPN_WORDS = re.compile(r"\b(vpn|proxy|tunnel|tor)\b", re.IGNORECASE)  # Word boundaries: "Mozilla" must not match
PROXY_HEADERS = ("via", "forwarded", "proxy-connection")
MAX_FORWARD_CHAIN = 2
TOR_EXIT_FILE = Path(__file__).parent / "data" / "tor-exits.txt"      # Optional: one IP per line

# Replay memory
_local: dict[str, float] = {}

def seen_before(key: str, ttl: int) -> bool:
    # True when the key was already stored; stores it otherwise. Redis first, in-process memory when Redis is down
    client = get_client()
    if client is not None:
        try:
            return client.set(key, 1, nx=True, ex=ttl) is None
        except redis.RedisError:
            pass

    now = time.monotonic()
    for expired in [k for k, until in _local.items() if until <= now]:
        del _local[expired]
    if key in _local:
        return True
    _local[key] = now + ttl
    return False

# GPS spoofing
def gps_signals(db: Session, student: Users, session: Sessions, latitude: float, longitude: float, accuracy: float | None) -> list[Signal]:
    signals = []
    now = datetime.now(timezone.utc)

    # Impossible travel: the previous stored check-in is too far away for the time that has passed
    last = (
        db.query(CheckIns)
        .filter(CheckIns.student_id == student.id, CheckIns.latitude.isnot(None), CheckIns.longitude.isnot(None))
        .order_by(CheckIns.checked_in_at.desc())
        .first()
    )
    if last is not None:
        meters = haversine_meters(last.latitude, last.longitude, latitude, longitude)
        seconds = max((now - as_utc(last.checked_in_at)).total_seconds(), 1)
        if meters > MIN_TRAVEL_METERS and meters / seconds > MAX_SPEED_MPS:
            signals.append(Signal(SignalTypes.IMPOSSIBLE_TRAVEL, Severity.CRITICAL, 0.5, {"distance_m": round(meters), "seconds": round(seconds)}))

    # Mock-location apps report a perfect fix
    if accuracy is not None and accuracy < MIN_PLAUSIBLE_ACCURACY_METERS:
        signals.append(Signal(SignalTypes.PATTERN_ANOMALY, Severity.MEDIUM, 0.2, {"reason": "implausible_gps_accuracy", "accuracy_m": accuracy}))

    # Several students on exactly the same coordinates in one session points to one spoofing tool
    same_spot = (
        db.query(CheckIns.id)
        .filter(
            CheckIns.session_id == session.id,
            CheckIns.student_id != student.id,
            CheckIns.latitude.between(latitude - CLUSTER_DEGREES, latitude + CLUSTER_DEGREES),
            CheckIns.longitude.between(longitude - CLUSTER_DEGREES, longitude + CLUSTER_DEGREES),
        )
        .count()
    )
    
    # Low weight on purpose: a whole class in one room can legitimately share a GPS fix, so this only adds to other signals
    if same_spot >= CLUSTER_STUDENTS:
        signals.append(Signal(SignalTypes.PATTERN_ANOMALY, Severity.LOW, 0.1, {"reason": "identical_coordinates", "students": same_spot}))

    return signals

# Replay attacks
def replay_signals(frames: list[str]) -> list[Signal]:
    if not frames:
        return []

    digest = hashlib.sha256("\x00".join(f.strip() for f in frames).encode()).hexdigest()
    if seen_before(f"replay:image:{digest}", IMAGE_TTL_SECONDS):
        return [Signal(SignalTypes.REPLAY_SUSPECTED, Severity.CRITICAL, 0.6, {"reason": "image_reused"})]
    return []

# VPN / proxy / Tor detection
@lru_cache(maxsize=1)
def _tor_exits() -> frozenset:
    try:
        with TOR_EXIT_FILE.open() as f:
            return frozenset(ipaddress.ip_address(line.strip()) for line in f if line.strip() and not line.startswith("#"))
    except (OSError, ValueError):
        return frozenset()

def network_signals(request: Request) -> list[Signal]:
    signals = []
    headers = request.headers

    if VPN_WORDS.search(headers.get("user-agent", "")):
        signals.append(Signal(SignalTypes.VPN_DETECTED, Severity.HIGH, 0.35, {"reason": "user_agent"}))

    if any(headers.get(name) for name in PROXY_HEADERS):
        signals.append(Signal(SignalTypes.PROXY_DETECTED, Severity.MEDIUM, 0.25, {"reason": "proxy_headers"}))

    forwarded = [part.strip() for part in headers.get("x-forwarded-for", "").split(",") if part.strip()]
    if len(forwarded) > MAX_FORWARD_CHAIN:
        signals.append(Signal(SignalTypes.PROXY_DETECTED, Severity.MEDIUM, 0.2, {"reason": "forward_chain", "hops": len(forwarded)}))

    # A private address only counts when the client claims it in the header: behind Docker the socket address is always private
    claimed = parse_ip(forwarded[0]) if forwarded else None
    if claimed is not None and claimed.is_private:
        signals.append(Signal(SignalTypes.SUSPICIOUS_IP, Severity.MEDIUM, 0.15, {"reason": "private_forwarded_address"}))

    if parse_ip(client_ip(request)) in _tor_exits():
        signals.append(Signal(SignalTypes.TOR_DETECTED, Severity.CRITICAL, 0.6))

    return signals
