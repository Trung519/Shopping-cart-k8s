"""Tests for OAuth2/OIDC authentication module."""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from product_catalog.auth import (
    CurrentUser,
    OIDCAuth,
    TokenPayload,
    require_admin,
    require_catalog_admin,
    require_group,
    require_role,
)


class TestCurrentUser:
    """Tests for CurrentUser model."""

    def test_has_role_exact_match(self):
        """Should return True for exact role match."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["platform-admin", "order-user"],
            groups=[],
        )
        assert user.has_role("platform-admin") is True
        assert user.has_role("order-user") is True

    def test_has_role_case_insensitive(self):
        """Should match roles case-insensitively."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["Platform-Admin"],
            groups=[],
        )
        assert user.has_role("platform-admin") is True
        assert user.has_role("PLATFORM-ADMIN") is True

    def test_has_role_not_found(self):
        """Should return False for non-existent role."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["order-user"],
            groups=[],
        )
        assert user.has_role("platform-admin") is False

    def test_has_any_role_with_match(self):
        """Should return True if user has any of the specified roles."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["order-user"],
            groups=[],
        )
        assert user.has_any_role("platform-admin", "order-user") is True

    def test_has_any_role_no_match(self):
        """Should return False if user has none of the specified roles."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-user"],
            groups=[],
        )
        assert user.has_any_role("platform-admin", "order-user") is False

    def test_in_group_exact_match(self):
        """Should return True for exact group match."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=[],
            groups=["platform-admins", "developers"],
        )
        assert user.in_group("platform-admins") is True
        assert user.in_group("developers") is True

    def test_in_group_with_path(self):
        """Should match groups with path prefixes."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=[],
            groups=["org/team/platform-admins"],
        )
        assert user.in_group("platform-admins") is True

    def test_in_group_not_found(self):
        """Should return False for non-existent group."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=[],
            groups=["developers"],
        )
        assert user.in_group("platform-admins") is False

    def test_is_admin_with_platform_admin_role(self):
        """Should return True for platform-admin role."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["platform-admin"],
            groups=[],
        )
        assert user.is_admin is True

    def test_is_admin_with_catalog_admin_role(self):
        """Should return True for catalog-admin role."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-admin"],
            groups=[],
        )
        assert user.is_admin is True

    def test_is_admin_with_admin_role(self):
        """Should return True for admin role."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["admin"],
            groups=[],
        )
        assert user.is_admin is True

    def test_is_admin_with_platform_admins_group(self):
        """Should return True for platform-admins group."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=[],
            groups=["platform-admins"],
        )
        assert user.is_admin is True

    def test_is_admin_regular_user(self):
        """Should return False for regular user."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-user"],
            groups=["users"],
        )
        assert user.is_admin is False

    def test_is_catalog_admin_with_role(self):
        """Should return True for catalog-admin role."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-admin"],
            groups=[],
        )
        assert user.is_catalog_admin is True

    def test_is_catalog_admin_with_platform_admin(self):
        """Should return True for platform-admin role."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["platform-admin"],
            groups=[],
        )
        assert user.is_catalog_admin is True

    def test_is_catalog_admin_with_group(self):
        """Should return True for catalog-admins group."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=[],
            groups=["catalog-admins"],
        )
        assert user.is_catalog_admin is True


class TestTokenPayload:
    """Tests for TokenPayload model."""

    def test_create_minimal_payload(self):
        """Should create payload with minimal required fields."""
        payload = TokenPayload(
            sub="user-123",
            exp=int(time.time()) + 3600,
            iat=int(time.time()),
            iss="http://keycloak/realms/test",
        )
        assert payload.sub == "user-123"
        assert payload.preferred_username is None

    def test_create_full_payload(self):
        """Should create payload with all fields."""
        payload = TokenPayload(
            sub="user-123",
            exp=int(time.time()) + 3600,
            iat=int(time.time()),
            iss="http://keycloak/realms/test",
            preferred_username="testuser",
            email="test@example.com",
            email_verified=True,
            name="Test User",
            given_name="Test",
            family_name="User",
            realm_access={"roles": ["admin"]},
            resource_access={"client": {"roles": ["manage"]}},
            groups=["/platform-admins"],
        )
        assert payload.preferred_username == "testuser"
        assert payload.email == "test@example.com"
        assert payload.groups == ["/platform-admins"]


class TestOIDCAuth:
    """Tests for OIDCAuth class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.oauth2_enabled = True
        settings.oauth2_issuer_uri = "http://keycloak.local/realms/test"
        settings.oauth2_jwks_uri = ""
        settings.oauth2_client_id = "test-client"
        return settings

    def test_enabled_property(self, mock_settings):
        """Should return OAuth2 enabled status from settings."""
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            assert auth.enabled is True

    def test_issuer_uri_property(self, mock_settings):
        """Should return issuer URI from settings."""
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            assert auth.issuer_uri == "http://keycloak.local/realms/test"

    def test_jwks_uri_property(self, mock_settings):
        """Should construct JWKS URI from issuer URI."""
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            expected = "http://keycloak.local/realms/test/protocol/openid-connect/certs"
            assert auth.jwks_uri == expected

    def test_jwks_uri_override(self, mock_settings):
        """Should allow an internal JWKS endpoint with a public token issuer."""
        mock_settings.oauth2_jwks_uri = "http://keycloak.internal/realms/test/certs"
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            assert auth.jwks_uri == "http://keycloak.internal/realms/test/certs"

    def test_clear_jwks_cache(self, mock_settings):
        """Should clear the JWKS cache."""
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            auth._jwks_cache = {"keys": []}
            auth.clear_jwks_cache()
            assert auth._jwks_cache is None

    def test_extract_user_with_realm_roles(self, mock_settings):
        """Should extract user with realm roles."""
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            payload = TokenPayload(
                sub="user-123",
                exp=int(time.time()) + 3600,
                iat=int(time.time()),
                iss="http://keycloak.local/realms/test",
                preferred_username="testuser",
                email="test@example.com",
                name="Test User",
                realm_access={"roles": ["platform-admin", "order-user"]},
            )

            user = auth.extract_user(payload)

            assert user.id == "user-123"
            assert user.username == "testuser"
            assert user.email == "test@example.com"
            assert "platform-admin" in user.roles
            assert "order-user" in user.roles

    def test_extract_user_with_resource_roles(self, mock_settings):
        """Should extract user with resource roles."""
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            payload = TokenPayload(
                sub="user-123",
                exp=int(time.time()) + 3600,
                iat=int(time.time()),
                iss="http://keycloak.local/realms/test",
                preferred_username="testuser",
                resource_access={
                    "catalog-service": {"roles": ["manage-products"]},
                    "account": {"roles": ["view-profile"]},
                },
            )

            user = auth.extract_user(payload)

            assert "manage-products" in user.roles
            assert "view-profile" in user.roles

    def test_extract_user_with_groups(self, mock_settings):
        """Should extract user with groups (removing leading slashes)."""
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            payload = TokenPayload(
                sub="user-123",
                exp=int(time.time()) + 3600,
                iat=int(time.time()),
                iss="http://keycloak.local/realms/test",
                preferred_username="testuser",
                groups=["/platform-admins", "/developers", "users"],
            )

            user = auth.extract_user(payload)

            assert "platform-admins" in user.groups
            assert "developers" in user.groups
            assert "users" in user.groups

    def test_extract_user_fallback_username(self, mock_settings):
        """Should fallback to sub if preferred_username is missing."""
        with patch("product_catalog.auth.get_settings", return_value=mock_settings):
            auth = OIDCAuth()
            payload = TokenPayload(
                sub="user-123",
                exp=int(time.time()) + 3600,
                iat=int(time.time()),
                iss="http://keycloak.local/realms/test",
            )

            user = auth.extract_user(payload)

            assert user.username == "user-123"


class TestRequireRoleDependency:
    """Tests for require_role dependency."""

    @pytest.mark.asyncio
    async def test_require_role_with_matching_role(self):
        """Should allow access when user has required role."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-admin"],
            groups=[],
        )

        check_roles = require_role("catalog-admin", "platform-admin")
        result = await check_roles(user)

        assert result == user

    @pytest.mark.asyncio
    async def test_require_role_without_matching_role(self):
        """Should raise 403 when user lacks required role."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-user"],
            groups=[],
        )

        check_roles = require_role("catalog-admin")

        with pytest.raises(HTTPException) as exc_info:
            await check_roles(user)

        assert exc_info.value.status_code == 403


class TestRequireGroupDependency:
    """Tests for require_group dependency."""

    @pytest.mark.asyncio
    async def test_require_group_with_matching_group(self):
        """Should allow access when user is in required group."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=[],
            groups=["platform-admins"],
        )

        check_groups = require_group("platform-admins", "developers")
        result = await check_groups(user)

        assert result == user

    @pytest.mark.asyncio
    async def test_require_group_without_matching_group(self):
        """Should raise 403 when user is not in required group."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=[],
            groups=["users"],
        )

        check_groups = require_group("platform-admins")

        with pytest.raises(HTTPException) as exc_info:
            await check_groups(user)

        assert exc_info.value.status_code == 403


class TestRequireAdminDependency:
    """Tests for require_admin dependency."""

    @pytest.mark.asyncio
    async def test_require_admin_with_admin_user(self):
        """Should allow access for admin user."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["platform-admin"],
            groups=[],
        )

        result = await require_admin(user)

        assert result == user

    @pytest.mark.asyncio
    async def test_require_admin_with_non_admin_user(self):
        """Should raise 403 for non-admin user."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-user"],
            groups=[],
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(user)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in str(exc_info.value.detail)


class TestRequireCatalogAdminDependency:
    """Tests for require_catalog_admin dependency."""

    @pytest.mark.asyncio
    async def test_require_catalog_admin_with_catalog_admin(self):
        """Should allow access for catalog admin."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-admin"],
            groups=[],
        )

        result = await require_catalog_admin(user)

        assert result == user

    @pytest.mark.asyncio
    async def test_require_catalog_admin_with_platform_admin(self):
        """Should allow access for platform admin."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["platform-admin"],
            groups=[],
        )

        result = await require_catalog_admin(user)

        assert result == user

    @pytest.mark.asyncio
    async def test_require_catalog_admin_with_non_admin(self):
        """Should raise 403 for non-catalog-admin user."""
        user = CurrentUser(
            id="user1",
            username="testuser",
            roles=["catalog-user"],
            groups=[],
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_catalog_admin(user)

        assert exc_info.value.status_code == 403
        assert "Catalog admin access required" in str(exc_info.value.detail)
