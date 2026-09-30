"""Authentication module for Product Catalog Service.

Supports Keycloak OIDC when enabled and local HS256 JWT tokens for the in-repo
login flow used during development.
"""

import logging
from functools import lru_cache
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from .config import get_settings

logger = logging.getLogger(__name__)

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT Token payload from Keycloak."""

    sub: str = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration time")
    iat: int = Field(..., description="Issued at time")
    iss: str = Field(..., description="Issuer")
    aud: str | list[str] = Field(default="account", description="Audience")
    preferred_username: str | None = Field(None, description="Username")
    email: str | None = Field(None, description="User email")
    email_verified: bool | None = Field(None, description="Email verified")
    name: str | None = Field(None, description="Full name")
    given_name: str | None = Field(None, description="First name")
    family_name: str | None = Field(None, description="Last name")
    realm_access: dict[str, Any] | None = Field(None, description="Realm roles")
    resource_access: dict[str, Any] | None = Field(None, description="Resource roles")
    groups: list[str] | None = Field(None, description="Group memberships")


class LocalTokenPayload(BaseModel):
    """Local HS256 JWT payload produced by basket-service login."""

    sub: str = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration time")
    iat: int = Field(..., description="Issued at time")
    email: str | None = Field(None, description="User email")
    name: str | None = Field(None, description="Display name")
    roles: list[str] = Field(default_factory=list, description="Local roles")


class CurrentUser(BaseModel):
    """Current authenticated user model."""

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str | None = Field(None, description="Email")
    name: str | None = Field(None, description="Full name")
    roles: list[str] = Field(default_factory=list, description="User roles")
    groups: list[str] = Field(default_factory=list, description="User groups")

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles or role.upper() in [r.upper() for r in self.roles]

    def has_any_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return any(self.has_role(role) for role in roles)

    def in_group(self, group: str) -> bool:
        """Check if user is in a specific group."""
        return group in self.groups or any(g.endswith(f"/{group}") for g in self.groups)

    @property
    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.has_any_role(
            "platform-admin", "catalog-admin", "admin", "cart-admin"
        ) or self.in_group("platform-admins")

    @property
    def is_catalog_admin(self) -> bool:
        """Check if user is a catalog admin."""
        return self.has_any_role("catalog-admin", "platform-admin", "cart-admin") or self.in_group(
            "catalog-admins"
        )


class OIDCAuth:
    """OIDC Authentication handler for Keycloak."""

    def __init__(self):
        self.settings = get_settings()
        self._jwks_cache: dict | None = None

    @property
    def enabled(self) -> bool:
        """Check if OAuth2 is enabled."""
        return self.settings.oauth2_enabled

    @property
    def issuer_uri(self) -> str:
        """Get the OIDC issuer URI."""
        return self.settings.oauth2_issuer_uri

    @property
    def jwks_uri(self) -> str:
        """Get the JWKS URI."""
        return self.settings.oauth2_jwks_uri or f"{self.issuer_uri}/protocol/openid-connect/certs"

    async def get_jwks(self) -> dict:
        """Fetch JWKS from Keycloak."""
        if self._jwks_cache is not None:
            return self._jwks_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_uri, timeout=10.0)
                response.raise_for_status()
                self._jwks_cache = response.json()
                return self._jwks_cache
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )

    def clear_jwks_cache(self) -> None:
        """Clear the JWKS cache."""
        self._jwks_cache = None

    async def verify_token(self, token: str) -> TokenPayload:
        """Verify and decode a JWT token."""
        try:
            jwks = await self.get_jwks()

            # Get the key ID from the token header
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            # Find the matching key in JWKS
            rsa_key = None
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    rsa_key = key
                    break

            if not rsa_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token signing key",
                )

            # Decode and verify the token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=self.settings.oauth2_client_id,
                issuer=self.issuer_uri,
                options={"verify_aud": False},  # Keycloak doesn't always include audience
            )

            return TokenPayload(**payload)

        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    def verify_local_token(self, token: str) -> LocalTokenPayload:
        """Verify and decode a local HS256 JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.settings.local_auth_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            return LocalTokenPayload(**payload)
        except JWTError as e:
            logger.warning(f"Local JWT verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    def extract_user(self, token_payload: TokenPayload) -> CurrentUser:
        """Extract user information from token payload."""
        # Extract realm roles
        roles = []
        if token_payload.realm_access:
            roles.extend(token_payload.realm_access.get("roles", []))

        # Extract resource roles
        if token_payload.resource_access:
            for resource, access in token_payload.resource_access.items():
                roles.extend(access.get("roles", []))

        # Extract groups (remove leading slashes)
        groups = []
        if token_payload.groups:
            groups = [g.lstrip("/") for g in token_payload.groups]

        return CurrentUser(
            id=token_payload.sub,
            username=token_payload.preferred_username or token_payload.sub,
            email=token_payload.email,
            name=token_payload.name,
            roles=roles,
            groups=groups,
        )

    def extract_local_user(self, token_payload: LocalTokenPayload) -> CurrentUser:
        """Extract user information from a local JWT token."""
        return CurrentUser(
            id=token_payload.sub,
            username=token_payload.email or token_payload.sub,
            email=token_payload.email,
            name=token_payload.name,
            roles=token_payload.roles,
            groups=[],
        )


# Global auth instance
@lru_cache
def get_oidc_auth() -> OIDCAuth:
    """Get the OIDC auth handler."""
    return OIDCAuth()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    oidc_auth: Annotated[OIDCAuth, Depends(get_oidc_auth)],
) -> CurrentUser | None:
    """Get the current authenticated user.

    Returns None if OAuth2 is disabled or no token provided.
    """
    if not credentials:
        return None

    if not oidc_auth.enabled:
        if not oidc_auth.settings.local_auth_enabled:
            return None
        token_payload = oidc_auth.verify_local_token(credentials.credentials)
        return oidc_auth.extract_local_user(token_payload)

    token_payload = await oidc_auth.verify_token(credentials.credentials)
    return oidc_auth.extract_user(token_payload)


async def require_auth(
    user: Annotated[CurrentUser | None, Depends(get_current_user)],
) -> CurrentUser:
    """Require authentication - raises 401 if not authenticated."""
    settings = get_settings()

    if not settings.oauth2_enabled:
        if user:
            return user
        # OAuth2 disabled - return anonymous user for development
        return CurrentUser(
            id="anonymous",
            username="anonymous",
            roles=["catalog-user"],
            groups=[],
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def require_admin(
    user: Annotated[CurrentUser, Depends(require_auth)],
) -> CurrentUser:
    """Require admin role."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_catalog_admin(
    user: Annotated[CurrentUser, Depends(require_auth)],
) -> CurrentUser:
    """Require catalog admin role."""
    if not user.is_catalog_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Catalog admin access required",
        )
    return user


def require_role(*roles: str):
    """Dependency that requires specific roles."""

    async def check_roles(
        user: Annotated[CurrentUser, Depends(require_auth)],
    ) -> CurrentUser:
        if not user.has_any_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(roles)}",
            )
        return user

    return check_roles


def require_group(*groups: str):
    """Dependency that requires membership in specific groups."""

    async def check_groups(
        user: Annotated[CurrentUser, Depends(require_auth)],
    ) -> CurrentUser:
        if not any(user.in_group(g) for g in groups):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required group membership: {', '.join(groups)}",
            )
        return user

    return check_groups
