import os
import time

import redis

from fastapi import HTTPException, status

# -----------------------------------------------------------------------------
# Redis rate limiting (ratelimit.py)
# -----------------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL")

LOGIN_PER_HOUR = int(os.getenv("RATE_LIMIT_LOGIN_PER_HOUR", 100000))
REGISTER_PER_HOUR = int(os.getenv("RATE_LIMIT_REGISTER_PER_HOUR", 100000))
API_PER_HOUR = int(os.getenv("RATE_LIMIT_API_PER_HOUR", 1000))
CHECKIN_PER_MINUTE = int(os.getenv("RATE_LIMIT_CHECKIN_PER_MINUTE", 10))

HOUR = 3600
MINUTE = 60
RETRY_REDIS_AFTER_SECONDS = 30

_client = None
_down_until = 0.0

def get_client():
    global _client
    if not REDIS_URL or time.monotonic() < _down_until:
        return None
    if _client is None:
        _client = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=0.3, socket_timeout=0.3)
    return _client

def hit(key: str, limit: int, window: int) -> tuple[bool, int]:
    global _down_until
    client = get_client()
    if client is None:
        return True, 0

    try:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = pipe.execute()
        if ttl is None or ttl < 0:
            client.expire(key, window)
            ttl = window
        return count <= limit, max(int(ttl), 1)
    except redis.RedisError:
        _down_until = time.monotonic() + RETRY_REDIS_AFTER_SECONDS
        return True, 0

def enforce(name: str, identity: str | None, limit: int, window: int) -> None:
    if not identity:
        return

    allowed, retry_after = hit(f"ratelimit:{name}:{identity}", limit, window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
