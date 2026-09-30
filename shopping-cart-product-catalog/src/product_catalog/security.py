"""Security middleware and utilities for Product Catalog service.

Provides protection against:
- DDoS (rate limiting)
- XSS (Cross-Site Scripting)
- Clickjacking
- Content sniffing
"""

import html
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

logger = structlog.get_logger(__name__)


# =============================================================================
# Rate Limiting
# =============================================================================


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""

    tokens: float
    last_update: float
    capacity: int
    refill_rate: float  # tokens per second

    def consume(self, tokens: int = 1) -> tuple[bool, float]:
        """
        Try to consume tokens from the bucket.

        Returns:
            Tuple of (success, wait_time_seconds)
        """
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_update = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        else:
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate
            return False, wait_time


class RateLimiter:
    """IP-based rate limiter using token bucket algorithm."""

    def __init__(
        self,
        requests_per_minute: int = 100,
        requests_per_second: int = 20,
        burst_capacity: int = 50,
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_second
        self.burst_capacity = burst_capacity
        self.buckets: dict[str, RateLimitBucket] = {}
        self._cleanup_counter = 0

    def _create_bucket(self) -> RateLimitBucket:
        """Create a new rate limit bucket."""
        return RateLimitBucket(
            tokens=self.burst_capacity,
            last_update=time.time(),
            capacity=self.burst_capacity,
            refill_rate=self.requests_per_second,
        )

    def is_allowed(self, client_ip: str) -> tuple[bool, float, int]:
        """
        Check if request from client_ip is allowed.

        Returns:
            Tuple of (allowed, wait_time, remaining_tokens)
        """
        # Periodic cleanup of old buckets
        self._cleanup_counter += 1
        if self._cleanup_counter >= 1000:
            self._cleanup_old_buckets()
            self._cleanup_counter = 0

        if client_ip not in self.buckets:
            self.buckets[client_ip] = self._create_bucket()

        bucket = self.buckets[client_ip]
        allowed, wait_time = bucket.consume(1)

        return allowed, wait_time, int(bucket.tokens)

    def _cleanup_old_buckets(self) -> None:
        """Remove buckets that haven't been used in over an hour."""
        now = time.time()
        stale_ips = [
            ip for ip, bucket in self.buckets.items() if now - bucket.last_update > 3600
        ]
        for ip in stale_ips:
            del self.buckets[ip]


@lru_cache
def get_rate_limiter() -> RateLimiter:
    """Get the singleton rate limiter."""
    settings = get_settings()
    return RateLimiter(
        requests_per_minute=getattr(settings, "rate_limit_per_minute", 100),
        requests_per_second=getattr(settings, "rate_limit_per_second", 20),
        burst_capacity=getattr(settings, "rate_limit_burst", 50),
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limiting per client IP."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health") or request.url.path.startswith("/live"):
            return await call_next(request)

        client_ip = get_client_ip(request)
        rate_limiter = get_rate_limiter()

        allowed, wait_time, remaining = rate_limiter.is_allowed(client_ip)

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                path=request.url.path,
                wait_seconds=wait_time,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many requests",
                    "message": f"Rate limit exceeded. Please retry after {int(wait_time) + 1} seconds.",
                },
                headers={
                    "Retry-After": str(int(wait_time) + 1),
                    "X-Rate-Limit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-Rate-Limit-Remaining"] = str(remaining)
        return response


def get_client_ip(request: Request) -> str:
    """Extract the real client IP, considering proxy headers."""
    # Check X-Forwarded-For (set by load balancers/proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP (set by nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to client host
    if request.client:
        return request.client.host

    return "unknown"


# =============================================================================
# Security Headers
# =============================================================================


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Prevent XSS attacks
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS (only in production with HTTPS)
        settings = get_settings()
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response


# =============================================================================
# Input Sanitization
# =============================================================================


# Pattern to detect potential script injection
SCRIPT_PATTERN = re.compile(
    r"<script[^>]*>.*?</script>|javascript:|on\w+\s*=",
    re.IGNORECASE | re.DOTALL,
)

# Pattern for valid safe text
SAFE_TEXT_PATTERN = re.compile(r"^[\w\s.,!?@#$%&*()\-_+=\[\]{}|;:'\"/\\]*$", re.UNICODE)


def escape_html(text: str | None) -> str | None:
    """Escape HTML entities to prevent XSS."""
    if text is None:
        return None
    return html.escape(text)


def remove_scripts(text: str | None) -> str | None:
    """Remove potential script content from input."""
    if text is None:
        return None
    return SCRIPT_PATTERN.sub("", text)


def sanitize_input(text: str | None) -> str | None:
    """Full sanitization: removes scripts and escapes HTML."""
    if text is None:
        return None
    return escape_html(remove_scripts(text))


def contains_xss_patterns(text: str | None) -> bool:
    """Check if input contains potential XSS patterns."""
    if text is None:
        return False
    return bool(SCRIPT_PATTERN.search(text))


def is_safe_text(text: str | None) -> bool:
    """Validate that input contains only safe characters."""
    if text is None:
        return True
    return bool(SAFE_TEXT_PATTERN.match(text))


# =============================================================================
# Setup Function
# =============================================================================


def setup_security(app: FastAPI) -> None:
    """Configure all security middleware for the FastAPI application."""
    # Add rate limiting (applied first)
    app.add_middleware(RateLimitMiddleware)

    # Add security headers (applied last, so headers are on all responses)
    app.add_middleware(SecurityHeadersMiddleware)

    logger.info("security_middleware_configured")
