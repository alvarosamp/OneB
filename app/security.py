"""HTTP security controls shared by the public FastAPI application."""

from __future__ import annotations

import secrets
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach a request id and browser protections to every API response.

    TLS itself is terminated by the reverse proxy/PaaS.  The API deliberately
    does not set HSTS here because it may also be used on plain HTTP locally.
    Configure HSTS at the production proxy once HTTPS is enforced end-to-end.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or secrets.token_hex(12)
        started_at = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
        response.headers["X-Response-Time-Ms"] = str(round((time.perf_counter() - started_at) * 1000, 1))
        return response
