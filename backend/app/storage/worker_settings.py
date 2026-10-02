import base64
import binascii
import re
from pathlib import Path
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import DEFAULT_SCANNER_SIGNING_KEY, DEFAULT_STORAGE_SIGNING_KEY


class StorageWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
        validate_default=True,
    )

    workloop_environment: Literal[
        "local",
        "test",
        "development",
        "shared-development",
        "staging",
        "production",
    ] = Field(validation_alias="WORKLOOP_ENVIRONMENT")
    workloop_data_class: Literal["synthetic-only"] = Field(validation_alias="WORKLOOP_DATA_CLASS")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    storage_backend: Literal["disabled", "synthetic", "spaces"] = Field(
        default="disabled", validation_alias="STORAGE_BACKEND"
    )
    storage_signing_key: SecretStr = Field(
        default=SecretStr(DEFAULT_STORAGE_SIGNING_KEY),
        validation_alias="STORAGE_SIGNING_KEY",
    )
    synthetic_storage_path: Path = Field(
        default=Path("/tmp/workloop-storage"),
        validation_alias="SYNTHETIC_STORAGE_PATH",
    )
    app_base_url: AnyHttpUrl = Field(
        default_factory=lambda: AnyHttpUrl("http://127.0.0.1:8000"),
        validation_alias="APP_BASE_URL",
    )
    spaces_endpoint_url: AnyHttpUrl | None = Field(
        default=None, validation_alias="SPACES_ENDPOINT_URL"
    )
    spaces_region: str | None = Field(default=None, validation_alias="SPACES_REGION")
    spaces_bucket: str | None = Field(default=None, validation_alias="SPACES_BUCKET")
    spaces_access_key: SecretStr | None = Field(default=None, validation_alias="SPACES_ACCESS_KEY")
    spaces_secret_key: SecretStr | None = Field(default=None, validation_alias="SPACES_SECRET_KEY")
    malware_scanner_backend: Literal["disabled", "synthetic"] = Field(
        default="disabled", validation_alias="MALWARE_SCANNER_BACKEND"
    )
    malware_scanner_definition: str = Field(
        default="synthetic-v1", validation_alias="MALWARE_SCANNER_DEFINITION"
    )
    malware_scanner_signing_key: SecretStr = Field(
        default=SecretStr(DEFAULT_SCANNER_SIGNING_KEY),
        validation_alias="MALWARE_SCANNER_SIGNING_KEY",
    )

    @model_validator(mode="after")
    def validate_worker_settings(self) -> Self:
        if not self.database_url.get_secret_value().startswith(
            ("postgresql://", "postgresql+psycopg://")
        ):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        self._validate_storage_settings()
        self._validate_scanner_settings()
        return self

    @staticmethod
    def _decode_32_byte_key(value: str, name: str) -> bytes:
        try:
            decoded = base64.b64decode(
                value + "=" * (-len(value) % 4),
                altchars=b"-_",
                validate=True,
            )
        except (ValueError, binascii.Error):
            raise ValueError(f"{name} must be unpadded base64url") from None
        if len(decoded) != 32 or "=" in value:
            raise ValueError(f"{name} must encode exactly 32 bytes")
        return decoded

    def _validate_storage_settings(self) -> None:
        if self.storage_backend == "disabled":
            return
        if self.storage_backend == "synthetic":
            if self.workloop_environment not in {"local", "test"}:
                raise ValueError("STORAGE_BACKEND synthetic is limited to local and test")
            self._decode_32_byte_key(
                self.storage_signing_key.get_secret_value(), "STORAGE_SIGNING_KEY"
            )
            if not self.synthetic_storage_path.is_absolute():
                raise ValueError("SYNTHETIC_STORAGE_PATH must be absolute")
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

    def _validate_scanner_settings(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", self.malware_scanner_definition):
            raise ValueError("MALWARE_SCANNER_DEFINITION is invalid")
        if self.malware_scanner_backend == "disabled":
            return
        if self.workloop_environment not in {"local", "test", "shared-development"}:
            raise ValueError(
                "MALWARE_SCANNER_BACKEND synthetic is limited to local, test, and "
                "synthetic-only shared development"
            )
        if (
            self.workloop_environment == "shared-development"
            and self.malware_scanner_signing_key.get_secret_value() == DEFAULT_SCANNER_SIGNING_KEY
        ):
            raise ValueError(
                "shared development scanner signing key must not use the local default"
            )
        self._decode_32_byte_key(
            self.malware_scanner_signing_key.get_secret_value(),
            "MALWARE_SCANNER_SIGNING_KEY",
        )

    def decoded_storage_signing_key(self) -> bytes:
        return self._decode_32_byte_key(
            self.storage_signing_key.get_secret_value(), "STORAGE_SIGNING_KEY"
        )

    def decoded_malware_scanner_signing_key(self) -> bytes:
        return self._decode_32_byte_key(
            self.malware_scanner_signing_key.get_secret_value(),
            "MALWARE_SCANNER_SIGNING_KEY",
        )
