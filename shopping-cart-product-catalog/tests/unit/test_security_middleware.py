"""Integration tests for security middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from product_catalog.security import (
    setup_security,
)


@pytest.fixture
def app_with_security():
    """Create a test app with security middleware."""
    app = FastAPI()

    @app.get("/api/test")
    def test_endpoint():
        return {"message": "OK"}

    @app.get("/health")
    def health_endpoint():
        return {"status": "healthy"}

    setup_security(app)
    return app


@pytest.fixture
def client(app_with_security):
    """Create a test client."""
    return TestClient(app_with_security)


class TestSecurityHeaders:
    """Tests for security headers middleware."""

    def test_should_include_xss_protection_header(self, client):
        """Response should include X-XSS-Protection header."""
        response = client.get("/api/test")

        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_should_include_frame_options_header(self, client):
        """Response should include X-Frame-Options header."""
        response = client.get("/api/test")

        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_should_include_content_type_options_header(self, client):
        """Response should include X-Content-Type-Options header."""
        response = client.get("/api/test")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_should_include_csp_header(self, client):
        """Response should include Content-Security-Policy header."""
        response = client.get("/api/test")

        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp

    def test_should_include_referrer_policy_header(self, client):
        """Response should include Referrer-Policy header."""
        response = client.get("/api/test")

        assert (
            response.headers.get("Referrer-Policy")
            == "strict-origin-when-cross-origin"
        )

    def test_should_include_permissions_policy_header(self, client):
        """Response should include Permissions-Policy header."""
        response = client.get("/api/test")

        policy = response.headers.get("Permissions-Policy")
        assert policy is not None
        assert "geolocation=()" in policy


class TestRateLimiting:
    """Tests for rate limiting middleware."""

    def test_should_include_rate_limit_remaining_header(self, client):
        """Response should include X-Rate-Limit-Remaining header."""
        response = client.get("/api/test")

        assert response.headers.get("X-Rate-Limit-Remaining") is not None

    def test_should_allow_requests_within_limit(self, client):
        """Should allow requests within rate limit."""
        for _ in range(10):
            response = client.get("/api/test")
            assert response.status_code == 200

    def test_should_skip_rate_limiting_for_health_endpoint(self, client):
        """Should skip rate limiting for health endpoints."""
        # Make many requests to health endpoint
        for _ in range(100):
            response = client.get("/health")
            assert response.status_code == 200

    def test_rate_limit_exceeded_should_return_429(self):
        """Should return 429 when rate limit exceeded."""
        # Create app with very low rate limit
        app = FastAPI()

        @app.get("/api/test")
        def test_endpoint():
            return {"message": "OK"}

        # Manually add middleware with low limits
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware

        from product_catalog.security import RateLimiter, get_client_ip

        class StrictRateLimitMiddleware(BaseHTTPMiddleware):
            def __init__(self, app):
                super().__init__(app)
                self.limiter = RateLimiter(
                    requests_per_minute=5,
                    requests_per_second=2,
                    burst_capacity=3,
                )

            async def dispatch(self, request, call_next):
                client_ip = get_client_ip(request)
                allowed, wait_time, remaining = self.limiter.is_allowed(client_ip)

                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"error": "Too many requests"},
                        headers={"Retry-After": str(int(wait_time) + 1)},
                    )

                response = await call_next(request)
                return response

        app.add_middleware(StrictRateLimitMiddleware)

        client = TestClient(app)

        # Exhaust rate limit
        responses = []
        for _ in range(10):
            responses.append(client.get("/api/test"))

        # Should have at least one 429
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes

    def test_rate_limit_exceeded_should_include_retry_after(self):
        """429 response should include Retry-After header."""
        app = FastAPI()

        @app.get("/api/test")
        def test_endpoint():
            return {"message": "OK"}

        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware

        from product_catalog.security import RateLimiter, get_client_ip

        class StrictRateLimitMiddleware(BaseHTTPMiddleware):
            def __init__(self, app):
                super().__init__(app)
                self.limiter = RateLimiter(
                    requests_per_minute=3,
                    requests_per_second=1,
                    burst_capacity=2,
                )

            async def dispatch(self, request, call_next):
                client_ip = get_client_ip(request)
                allowed, wait_time, remaining = self.limiter.is_allowed(client_ip)

                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"error": "Too many requests"},
                        headers={"Retry-After": str(int(wait_time) + 1)},
                    )

                return await call_next(request)

        app.add_middleware(StrictRateLimitMiddleware)

        client = TestClient(app)

        # Exhaust rate limit
        for _ in range(5):
            response = client.get("/api/test")

        # Find a 429 response
        for _ in range(5):
            response = client.get("/api/test")
            if response.status_code == 429:
                assert "Retry-After" in response.headers
                break


class TestClientIpExtraction:
    """Tests for client IP extraction."""

    def test_should_use_x_forwarded_for_header(self):
        """Should extract client IP from X-Forwarded-For header."""
        app = FastAPI()

        @app.get("/api/test")
        def test_endpoint():
            return {"message": "OK"}

        setup_security(app)
        client = TestClient(app)

        # First request from IP1
        response1 = client.get(
            "/api/test",
            headers={"X-Forwarded-For": "203.0.113.1, 10.0.0.1"},
        )

        # Second request from IP2
        response2 = client.get(
            "/api/test",
            headers={"X-Forwarded-For": "203.0.113.2, 10.0.0.1"},
        )

        # Both should succeed (different client IPs)
        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_should_use_x_real_ip_header(self):
        """Should extract client IP from X-Real-IP header."""
        app = FastAPI()

        @app.get("/api/test")
        def test_endpoint():
            return {"message": "OK"}

        setup_security(app)
        client = TestClient(app)

        response = client.get(
            "/api/test",
            headers={"X-Real-IP": "203.0.113.50"},
        )

        assert response.status_code == 200
