from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# -----------------------------------------------------------------------------
# Security headers (middleware.py)
# -----------------------------------------------------------------------------

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Cross-Origin-Resource-Policy": "same-site",
}

# The JSON API serves no HTML, so a strict policy is safe; the interactive docs need their CDN assets.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_CSP = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        response.headers.setdefault("Content-Security-Policy", DOCS_CSP if request.url.path.startswith(DOCS_PATHS) else API_CSP)

        # API responses carry personal data and must not be cached
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")

        return response
