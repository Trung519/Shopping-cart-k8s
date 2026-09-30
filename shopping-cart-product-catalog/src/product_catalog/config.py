"""Configuration management for Product Catalog service."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "product-catalog"
    debug: bool = False
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Database
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="products", alias="DB_NAME")
    db_username: str = Field(default="postgres", alias="DB_USERNAME")
    db_password: str = Field(default="postgres", alias="DB_PASSWORD")

    @property
    def database_url(self) -> str:
        """Generate SQLAlchemy database URL."""
        return (
            f"postgresql://{self.db_username}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # RabbitMQ
    rabbitmq_host: str = Field(default="localhost", alias="RABBITMQ_HOST")
    rabbitmq_port: int = Field(default=5672, alias="RABBITMQ_PORT")
    rabbitmq_vhost: str = Field(default="/", alias="RABBITMQ_VHOST")
    rabbitmq_username: str = Field(default="guest", alias="RABBITMQ_USERNAME")
    rabbitmq_password: str = Field(default="guest", alias="RABBITMQ_PASSWORD")
    rabbitmq_use_tls: bool = Field(default=False, alias="RABBITMQ_USE_TLS")

    # Vault
    vault_enabled: bool = Field(default=False, alias="VAULT_ENABLED")
    vault_addr: str = Field(default="http://localhost:8200", alias="VAULT_ADDR")
    vault_role: str = Field(default="product-publisher", alias="VAULT_ROLE")
    vault_rabbitmq_path: str = Field(default="rabbitmq", alias="VAULT_RABBITMQ_PATH")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=100, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_second: int = Field(default=20, alias="RATE_LIMIT_PER_SECOND")
    rate_limit_burst: int = Field(default=50, alias="RATE_LIMIT_BURST")

    # OAuth2/OIDC Configuration (Keycloak SSO)
    oauth2_enabled: bool = Field(default=False, alias="OAUTH2_ENABLED")
    oauth2_issuer_uri: str = Field(
        default="http://keycloak.identity.svc.cluster.local/realms/shopping-cart",
        alias="OAUTH2_ISSUER_URI"
    )
    oauth2_jwks_uri: str = Field(default="", alias="OAUTH2_JWKS_URI")
    oauth2_client_id: str = Field(default="product-catalog", alias="OAUTH2_CLIENT_ID")
    oauth2_client_secret: str = Field(default="", alias="OAUTH2_CLIENT_SECRET")

    # Local JWT auth used by the in-repo login flow
    local_auth_enabled: bool = Field(default=True, alias="LOCAL_AUTH_ENABLED")
    local_auth_jwt_secret: str = Field(default="change-me-in-prod", alias="LOCAL_AUTH_JWT_SECRET")
    internal_api_token: str = Field(default="change-me-in-prod", alias="INTERNAL_API_TOKEN")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
