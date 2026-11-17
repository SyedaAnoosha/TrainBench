"""Middleware for correlation IDs, rate limiting, security headers, and error formatting."""
import re
import time
import uuid
from collections import deque
from typing import Deque, Dict, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.config import settings
from backend.observability.logging import get_correlation_id, logger, set_correlation_id

_CID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract existing correlation ID or generate new; sanitize to a safe charset.
        cid = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or ""
        if not _CID_PATTERN.match(cid):
            cid = str(uuid.uuid4())
        set_correlation_id(cid)

        start_time = time.time()
        try:
            response = await call_next(request)
            duration_ms = int((time.time() - start_time) * 1000)
            response.headers["X-Correlation-ID"] = cid
            response.headers["X-Response-Time-MS"] = str(duration_ms)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"

            # Structured logging
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
                extra={"duration_ms": duration_ms},
            )
            return response
        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Unhandled error processing {request.method} {request.url.path}: {exc}")
            return JSONResponse(
                status_code=500,
                content={
                    "type": "https://trainbench.dev/errors/internal-server-error",
                    "title": "Internal Server Error",
                    "status": 500,
                    "detail": "An unexpected error occurred while processing your request.",
                    "correlation_id": cid,
                },
                headers={
                    "X-Correlation-ID": cid,
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "Referrer-Policy": "no-referrer",
                },
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP rate limit for write (non-GET) API requests."""

    instance: Optional["RateLimitMiddleware"] = None

    def __init__(self, app, limit_per_minute: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.limit = limit_per_minute
        self.window = window_seconds
        self._hits: Dict[str, Deque[float]] = {}
        RateLimitMiddleware.instance = self

    @classmethod
    def reset(cls) -> None:
        if cls.instance:
            cls.instance._hits.clear()

    async def dispatch(self, request: Request, call_next):
        if (
            self.limit <= 0
            or request.method in ("GET", "HEAD", "OPTIONS")
            or not request.url.path.startswith("/api/")
        ):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        now = time.time()
        hits = self._hits.setdefault(ip, deque())
        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded — too many requests"},
            )
        hits.append(now)

        # Bound memory: drop state for idle IPs occasionally.
        if len(self._hits) > 10000:
            self._hits = {k: v for k, v in self._hits.items() if v}

        return await call_next(request)
