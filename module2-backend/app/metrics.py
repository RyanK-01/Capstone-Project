import time

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# -----------------------------------------------------------------------------
# Prometheus metrics (metrics.py)
# -----------------------------------------------------------------------------

METRICS_PATH = "/metrics"

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "route", "status"],
)
CHECKIN_ATTEMPTS = Counter("checkin_attempts_total", "Check-in submissions received, including refused ones")
CHECKIN_SUCCESS = Counter("checkin_success_total", "Check-ins that were approved")

metrics_router = APIRouter()

@metrics_router.get(METRICS_PATH, include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == METRICS_PATH:
            await self.app(scope, receive, send)
            return

        status_code = 500 
        start = time.perf_counter()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            REQUEST_DURATION.labels(scope["method"], getattr(route, "path", "unmatched"), str(status_code)).observe(time.perf_counter() - start)
