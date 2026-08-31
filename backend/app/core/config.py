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
    application_user_lookup_timeout_seconds: float = Field(
        default=5.0, validation_alias="APPLICATION_USER_LOOKUP_TIMEOUT_SECONDS"
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

    @model_validator(mode="after")
    def validate_database_settings(self) -> Self:
        database_url = self.database_url.get_secret_value()
        if not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        if not 0 < self.database_health_timeout_seconds <= 30:
            raise ValueError("DATABASE_HEALTH_TIMEOUT_SECONDS must be between 0 and 30")
        if not 0 < self.application_user_lookup_timeout_seconds <= 30:
            raise ValueError("APPLICATION_USER_LOOKUP_TIMEOUT_SECONDS must be between 0 and 30")
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
        return self
