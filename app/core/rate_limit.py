import os
import time
import logging
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def _rate_limit_enabled() -> bool:
    return os.environ.get("RATE_LIMIT_ENABLED", "true").strip().lower() not in {"0", "false", "no"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter.

    Limits requests per IP address within a sliding window, but only for the
    paths listed in `limit_paths`. By default only the auth endpoints are
    rate-limited, so normal dashboard/API usage is never throttled.

    Set RATE_LIMIT_ENABLED=false to disable entirely (used by the test suite).

    For production, replace with Redis-based rate limiting.
    """

    def __init__(
        self,
        app,
        max_requests: int = 60,
        window_seconds: int = 60,
        limit_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.limit_paths = limit_paths or []
        self.exclude_paths = exclude_paths or ["/static", "/uploads"]
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if not _rate_limit_enabled():
            return await call_next(request)

        for prefix in self.exclude_paths:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        if self.limit_paths and not any(
            request.url.path.startswith(prefix) for prefix in self.limit_paths
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        timestamps = self._requests[client_ip]
        timestamps[:] = [t for t in timestamps if t > window_start]

        if len(timestamps) >= self.max_requests:
            logger.warning("Rate limit exceeded for %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after_seconds": int(timestamps[0] + self.window_seconds - now),
                },
            )

        timestamps.append(now)
        return await call_next(request)
