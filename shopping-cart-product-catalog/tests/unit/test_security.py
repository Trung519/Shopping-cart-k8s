"""Unit tests for security module."""

import time

import pytest

from product_catalog.security import (
    RateLimitBucket,
    RateLimiter,
    contains_xss_patterns,
    escape_html,
    is_safe_text,
    remove_scripts,
    sanitize_input,
)


class TestRateLimitBucket:
    """Tests for RateLimitBucket token bucket implementation."""

    def test_should_allow_requests_within_capacity(self):
        """Bucket should allow requests when tokens available."""
        bucket = RateLimitBucket(
            tokens=10.0,
            last_update=time.time(),
            capacity=10,
            refill_rate=1.0,
        )

        allowed, wait_time = bucket.consume(1)

        assert allowed is True
        assert wait_time == 0.0
        assert bucket.tokens == 9.0

    def test_should_block_when_no_tokens(self):
        """Bucket should block when tokens exhausted."""
        bucket = RateLimitBucket(
            tokens=0.0,
            last_update=time.time(),
            capacity=10,
            refill_rate=1.0,
        )

        allowed, wait_time = bucket.consume(1)

        assert allowed is False
        assert wait_time > 0

    def test_should_refill_tokens_over_time(self):
        """Bucket should refill tokens based on elapsed time."""
        bucket = RateLimitBucket(
            tokens=0.0,
            last_update=time.time() - 5.0,  # 5 seconds ago
            capacity=10,
            refill_rate=2.0,  # 2 tokens/second
        )

        allowed, wait_time = bucket.consume(1)

        # Should have refilled ~10 tokens (5 sec * 2 tokens/sec)
        assert allowed is True

    def test_should_not_exceed_capacity(self):
        """Bucket should not refill beyond capacity."""
        bucket = RateLimitBucket(
            tokens=5.0,
            last_update=time.time() - 100.0,  # Long time ago
            capacity=10,
            refill_rate=10.0,
        )

        bucket.consume(0)  # Trigger refill

        assert bucket.tokens <= bucket.capacity


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_should_allow_first_request(self):
        """Rate limiter should allow first request from new IP."""
        limiter = RateLimiter(
            requests_per_minute=100,
            requests_per_second=10,
            burst_capacity=20,
        )

        allowed, wait_time, remaining = limiter.is_allowed("192.168.1.1")

        assert allowed is True
        assert wait_time == 0.0
        assert remaining > 0

    def test_should_track_ips_independently(self):
        """Rate limiter should track each IP separately."""
        limiter = RateLimiter(
            requests_per_minute=5,
            requests_per_second=2,
            burst_capacity=3,
        )

        # Exhaust IP1
        for _ in range(5):
            limiter.is_allowed("192.168.1.1")

        # IP2 should still be allowed
        allowed, _, _ = limiter.is_allowed("192.168.1.2")

        assert allowed is True

    def test_should_block_after_burst_exhausted(self):
        """Rate limiter should block after burst capacity exhausted."""
        limiter = RateLimiter(
            requests_per_minute=100,
            requests_per_second=10,
            burst_capacity=3,
        )

        # Exhaust burst capacity
        for _ in range(5):
            limiter.is_allowed("192.168.1.1")

        allowed, wait_time, remaining = limiter.is_allowed("192.168.1.1")

        assert allowed is False
        assert wait_time > 0
        assert remaining == 0


class TestXssPrevention:
    """Tests for XSS prevention utilities."""

    def test_escape_html_should_handle_none(self):
        """escape_html should return None for None input."""
        assert escape_html(None) is None

    def test_escape_html_should_escape_tags(self):
        """escape_html should escape HTML tags."""
        result = escape_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escape_html_should_escape_special_chars(self):
        """escape_html should escape special characters."""
        assert "&amp;" in escape_html("Tom & Jerry")
        assert "&lt;" in escape_html("a < b")
        assert "&gt;" in escape_html("a > b")
        assert "&quot;" in escape_html('Say "Hello"')

    def test_remove_scripts_should_handle_none(self):
        """remove_scripts should return None for None input."""
        assert remove_scripts(None) is None

    def test_remove_scripts_should_remove_script_tags(self):
        """remove_scripts should remove script tags."""
        result = remove_scripts("Hello <script>evil()</script> World")
        assert "<script>" not in result
        assert "evil()" not in result
        assert "Hello" in result
        assert "World" in result

    def test_remove_scripts_should_remove_javascript_urls(self):
        """remove_scripts should remove javascript: URLs."""
        result = remove_scripts("javascript:alert('xss')")
        assert "javascript:" not in result

    def test_remove_scripts_should_remove_event_handlers(self):
        """remove_scripts should remove inline event handlers."""
        result = remove_scripts('<img onerror="alert(1)">')
        assert "onerror=" not in result

    @pytest.mark.parametrize(
        "malicious_input",
        [
            "<script>alert('xss')</script>",
            "<SCRIPT>alert('xss')</SCRIPT>",
            "<script src='evil.js'></script>",
            "javascript:alert('xss')",
            "JAVASCRIPT:alert('xss')",
            "<img onerror=alert(1)>",
            "<div onclick=alert(1)>",
            "<a onmouseover=alert(1)>",
        ],
    )
    def test_contains_xss_patterns_should_detect_attacks(self, malicious_input):
        """contains_xss_patterns should detect XSS attack patterns."""
        assert contains_xss_patterns(malicious_input) is True

    @pytest.mark.parametrize(
        "safe_input",
        [
            "Hello, World!",
            "Order #12345",
            "Price: $29.99",
            "user@example.com",
            "Normal product description",
            "JavaScript is a language",  # Contains word but not pattern
        ],
    )
    def test_contains_xss_patterns_should_allow_safe_text(self, safe_input):
        """contains_xss_patterns should not flag safe text."""
        assert contains_xss_patterns(safe_input) is False

    def test_sanitize_input_should_remove_and_escape(self):
        """sanitize_input should remove scripts and escape HTML."""
        result = sanitize_input("Hello <script>evil()</script> & <b>World</b>")

        assert "<script>" not in result
        assert "evil()" not in result
        assert "&amp;" in result
        assert "&lt;b&gt;" in result

    def test_is_safe_text_should_handle_none(self):
        """is_safe_text should return True for None."""
        assert is_safe_text(None) is True

    def test_is_safe_text_should_accept_normal_text(self):
        """is_safe_text should accept normal text."""
        assert is_safe_text("Hello World") is True
        assert is_safe_text("Order #123") is True
        assert is_safe_text("Price: $29.99") is True

    def test_sanitize_should_preserve_safe_content(self):
        """sanitize_input should preserve safe content."""
        safe_input = "Customer: John Doe, Order: #12345"
        assert sanitize_input(safe_input) == safe_input
