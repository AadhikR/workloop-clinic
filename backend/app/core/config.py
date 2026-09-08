import re
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore", populate_by_name=True)

    app_env: Literal["local", "test", "development", "staging", "production"] = Field(
        validation_alias="APP_ENV"
    )
    app_base_url: AnyHttpUrl = Field(validation_alias="APP_BASE_URL")
    frontend_url: AnyHttpUrl = Field(validation_alias="FRONTEND_URL")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )
    database_health_timeout_seconds: float = Field(
        default=5.0, validation_alias="DATABASE_HEALTH_TIMEOUT_SECONDS"
    )
    api_request_timeout_seconds: float = Field(
        default=15.0, validation_alias="API_REQUEST_TIMEOUT_SECONDS"
    )
    application_user_lookup_timeout_seconds: float = Field(
        default=5.0, validation_alias="APPLICATION_USER_LOOKUP_TIMEOUT_SECONDS"
    )
    authorization_context_setup_timeout_seconds: float = Field(
        default=5.0, validation_alias="AUTHORIZATION_CONTEXT_SETUP_TIMEOUT_SECONDS"
    )
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    oidc_issuer: AnyHttpUrl = Field(validation_alias="OIDC_ISSUER")
    oidc_audience: str = Field(validation_alias="OIDC_AUDIENCE")
    oidc_jwks_url: AnyHttpUrl = Field(validation_alias="OIDC_JWKS_URL")
    oidc_jwks_connect_timeout_seconds: float = Field(
        default=2.0, validation_alias="OIDC_JWKS_CONNECT_TIMEOUT_SECONDS"
    )
    oidc_jwks_read_timeout_seconds: float = Field(
        default=2.0, validation_alias="OIDC_JWKS_READ_TIMEOUT_SECONDS"
    )
    oidc_jwks_total_timeout_seconds: float = Field(
        default=5.0, validation_alias="OIDC_JWKS_TOTAL_TIMEOUT_SECONDS"
    )
    oidc_jwks_cache_ttl_seconds: float = Field(
        default=300.0, validation_alias="OIDC_JWKS_CACHE_TTL_SECONDS"
    )
    oidc_jwks_refresh_cooldown_seconds: float = Field(
        default=1.0, validation_alias="OIDC_JWKS_REFRESH_COOLDOWN_SECONDS"
    )
    trusted_proxy: Literal["direct", "digitalocean_app_platform"] = Field(
        default="direct", validation_alias="TRUSTED_PROXY"
    )
    storage_backend: Literal["disabled", "spaces"] = Field(
        default="disabled", validation_alias="STORAGE_BACKEND"
    )
    spaces_endpoint_url: AnyHttpUrl | None = Field(
        default=None, validation_alias="SPACES_ENDPOINT_URL"
    )
    spaces_region: str | None = Field(default=None, validation_alias="SPACES_REGION")
    spaces_bucket: str | None = Field(default=None, validation_alias="SPACES_BUCKET")
    spaces_access_key: SecretStr | None = Field(default=None, validation_alias="SPACES_ACCESS_KEY")
    spaces_secret_key: SecretStr | None = Field(default=None, validation_alias="SPACES_SECRET_KEY")

    @model_validator(mode="after")
    def validate_database_settings(self) -> Self:
        database_url = self.database_url.get_secret_value()
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        if not 0 < self.database_health_timeout_seconds <= 5:
            raise ValueError("DATABASE_HEALTH_TIMEOUT_SECONDS must be between 0 and 5")
        if not 0 < self.api_request_timeout_seconds <= 15:
            raise ValueError("API_REQUEST_TIMEOUT_SECONDS must be between 0 and 15")
        if not 0 < self.application_user_lookup_timeout_seconds <= 30:
            raise ValueError("APPLICATION_USER_LOOKUP_TIMEOUT_SECONDS must be between 0 and 30")
        if not 0 < self.authorization_context_setup_timeout_seconds <= 30:
            raise ValueError("AUTHORIZATION_CONTEXT_SETUP_TIMEOUT_SECONDS must be between 0 and 30")
        if str(self.oidc_issuer).endswith("/"):
            raise ValueError("OIDC_ISSUER must not end with a slash")
        for setting_name, url in (
            ("OIDC_ISSUER", self.oidc_issuer),
            ("OIDC_JWKS_URL", self.oidc_jwks_url),
        ):
            if url.username or url.password or url.query or url.fragment:
                raise ValueError(
                    f"{setting_name} must not contain credentials, a query, or a fragment"
                )
        if self.app_env not in {"local", "test"} and (
            self.oidc_issuer.scheme != "https" or self.oidc_jwks_url.scheme != "https"
        ):
            raise ValueError("OIDC_ISSUER and OIDC_JWKS_URL must use HTTPS outside local and test")
        if self.app_env not in {"local", "test"} and (
            self.app_base_url.scheme != "https" or self.frontend_url.scheme != "https"
        ):
            raise ValueError("APP_BASE_URL and FRONTEND_URL must use HTTPS outside local and test")
        if not self.oidc_audience or any(character.isspace() for character in self.oidc_audience):
            raise ValueError("OIDC_AUDIENCE must be a non-empty value without whitespace")
        if not 0 < self.oidc_jwks_connect_timeout_seconds <= 10:
            raise ValueError("OIDC_JWKS_CONNECT_TIMEOUT_SECONDS must be between 0 and 10")
        if not 0 < self.oidc_jwks_read_timeout_seconds <= 10:
            raise ValueError("OIDC_JWKS_READ_TIMEOUT_SECONDS must be between 0 and 10")
        if not 0 < self.oidc_jwks_total_timeout_seconds <= 30:
            raise ValueError("OIDC_JWKS_TOTAL_TIMEOUT_SECONDS must be between 0 and 30")
        if not 1 <= self.oidc_jwks_cache_ttl_seconds <= 3600:
            raise ValueError("OIDC_JWKS_CACHE_TTL_SECONDS must be between 1 and 3600")
        if not 0.1 <= self.oidc_jwks_refresh_cooldown_seconds <= 60:
            raise ValueError("OIDC_JWKS_REFRESH_COOLDOWN_SECONDS must be between 0.1 and 60")
        if self.app_env in {"local", "test"} and str(self.frontend_url).rstrip("/") != (
            "http://127.0.0.1:5174"
        ):
            raise ValueError("FRONTEND_URL must be http://127.0.0.1:5174 in local and test")
        for setting_name, url in (
            ("APP_BASE_URL", self.app_base_url),
            ("FRONTEND_URL", self.frontend_url),
        ):
            if url.username or url.password or url.query or url.fragment:
                raise ValueError(
                    f"{setting_name} must not contain credentials, a query, or a fragment"
                )
            if url.path not in {"", "/"}:
                raise ValueError(f"{setting_name} must be an origin without a path")
        if self.app_env not in {"local", "test"} and self.trusted_proxy != (
            "digitalocean_app_platform"
        ):
            raise ValueError("TRUSTED_PROXY must identify DigitalOcean App Platform when deployed")
        self._validate_storage_settings()
        return self

    def _validate_storage_settings(self) -> None:
        if self.storage_backend == "disabled":
            return
        required = {
            "SPACES_ENDPOINT_URL": self.spaces_endpoint_url,
            "SPACES_REGION": self.spaces_region,
            "SPACES_BUCKET": self.spaces_bucket,
            "SPACES_ACCESS_KEY": self.spaces_access_key,
            "SPACES_SECRET_KEY": self.spaces_secret_key,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError(f"Spaces configuration is incomplete: {', '.join(sorted(missing))}")
        assert self.spaces_endpoint_url is not None
        assert self.spaces_region is not None
        assert self.spaces_bucket is not None
        if self.spaces_endpoint_url.scheme != "https":
            raise ValueError("SPACES_ENDPOINT_URL must use HTTPS")
        if self.spaces_endpoint_url.host != f"{self.spaces_region}.digitaloceanspaces.com":
            raise ValueError("SPACES_ENDPOINT_URL must match SPACES_REGION")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{1,61}[a-z0-9])?", self.spaces_bucket):
            raise ValueError("SPACES_BUCKET must be a valid lowercase bucket name")

    @property
    def cors_allowed_origins(self) -> tuple[str, ...]:
        if self.app_env in {"local", "test"}:
            return ("http://127.0.0.1:5174",)
        return (str(self.frontend_url).rstrip("/"),)
