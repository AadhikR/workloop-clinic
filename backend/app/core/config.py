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
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")

    @model_validator(mode="after")
    def validate_database_settings(self) -> Self:
        database_url = self.database_url.get_secret_value()
        if not database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        if not 0 < self.database_health_timeout_seconds <= 30:
            raise ValueError("DATABASE_HEALTH_TIMEOUT_SECONDS must be between 0 and 30")
        return self
