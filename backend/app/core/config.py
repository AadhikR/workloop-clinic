import base64
import binascii
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_RECOVERY_KEY_ID = "00000000"
DEFAULT_RECOVERY_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA"
DEFAULT_STORAGE_SIGNING_KEY = "MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTE"
DEFAULT_ATTACHMENT_OBJECT_KEY_HMAC_KEY = "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjI"
DEFAULT_SCANNER_SIGNING_KEY = "MzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM"


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class PreviousRecoveryKey(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, extra="forbid")

    key_id: str
    key: SecretStr
    accept_until: datetime


def _empty_previous_recovery_keys() -> list[PreviousRecoveryKey]:
    return []


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
    cursor_signing_key: SecretStr = Field(validation_alias="CURSOR_SIGNING_KEY")
    idempotency_recovery_current_key_id: str = Field(
        default=DEFAULT_RECOVERY_KEY_ID,
        validation_alias="IDEMPOTENCY_RECOVERY_CURRENT_KEY_ID",
    )
    idempotency_recovery_current_key: SecretStr = Field(
        default=SecretStr(DEFAULT_RECOVERY_KEY),
        validation_alias="IDEMPOTENCY_RECOVERY_CURRENT_KEY",
    )
    idempotency_recovery_previous_keys: list[PreviousRecoveryKey] = Field(
        default_factory=_empty_previous_recovery_keys,
        validation_alias="IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS",
    )
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
    storage_backend: Literal["disabled", "synthetic", "spaces"] = Field(
        default="disabled", validation_alias="STORAGE_BACKEND"
    )
    storage_signing_key: SecretStr = Field(
        default=SecretStr(DEFAULT_STORAGE_SIGNING_KEY),
        validation_alias="STORAGE_SIGNING_KEY",
    )
    attachment_object_key_hmac_key: SecretStr = Field(
        default=SecretStr(DEFAULT_ATTACHMENT_OBJECT_KEY_HMAC_KEY),
        validation_alias="ATTACHMENT_OBJECT_KEY_HMAC_KEY",
    )
    synthetic_storage_path: Path = Field(
        default=Path("/tmp/workloop-storage"),
        validation_alias="SYNTHETIC_STORAGE_PATH",
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
    def validate_database_settings(self) -> Self:
        database_url = self.database_url.get_secret_value()
        if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        cursor_key = self.cursor_signing_key.get_secret_value()
        try:
            decoded_cursor_key = base64.b64decode(
                cursor_key + "=" * (-len(cursor_key) % 4),
                altchars=b"-_",
                validate=True,
            )
        except (ValueError, binascii.Error):
            raise ValueError("CURSOR_SIGNING_KEY must be unpadded base64url") from None
        if len(decoded_cursor_key) != 32 or "=" in cursor_key:
            raise ValueError("CURSOR_SIGNING_KEY must encode exactly 32 bytes")
        self._validate_idempotency_recovery_keys()
        if self.app_env not in {"local", "test"} and (
            self.idempotency_recovery_current_key_id == DEFAULT_RECOVERY_KEY_ID
            or self.idempotency_recovery_current_key.get_secret_value() == DEFAULT_RECOVERY_KEY
        ):
            raise ValueError("deployed idempotency recovery key must not use the local default")
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

    def _validate_idempotency_recovery_keys(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{8}", self.idempotency_recovery_current_key_id):
            raise ValueError(
                "IDEMPOTENCY_RECOVERY_CURRENT_KEY_ID must be eight lowercase hex digits"
            )
        self._decode_32_byte_key(
            self.idempotency_recovery_current_key.get_secret_value(),
            "IDEMPOTENCY_RECOVERY_CURRENT_KEY",
        )
        identifiers = {self.idempotency_recovery_current_key_id}
        for previous in self.idempotency_recovery_previous_keys:
            if not re.fullmatch(r"[0-9a-f]{8}", previous.key_id):
                raise ValueError(
                    "IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS keyId must be eight lowercase hex digits"
                )
            if previous.key_id in identifiers:
                raise ValueError("IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS keyId must be unique")
            identifiers.add(previous.key_id)
            self._decode_32_byte_key(
                previous.key.get_secret_value(),
                "IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS key",
            )
            if (
                previous.accept_until.tzinfo is None
                or previous.accept_until.utcoffset() != UTC.utcoffset(previous.accept_until)
            ):
                raise ValueError("IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS acceptUntil must include UTC")

    def decoded_idempotency_recovery_key(self) -> bytes:
        return self._decode_32_byte_key(
            self.idempotency_recovery_current_key.get_secret_value(),
            "IDEMPOTENCY_RECOVERY_CURRENT_KEY",
        )

    def decoded_previous_idempotency_recovery_keys(self) -> list[tuple[str, bytes, datetime]]:
        return [
            (
                previous.key_id,
                self._decode_32_byte_key(
                    previous.key.get_secret_value(),
                    "IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS key",
                ),
                previous.accept_until.astimezone(UTC),
            )
            for previous in self.idempotency_recovery_previous_keys
        ]

    def _validate_storage_settings(self) -> None:
        if self.storage_backend == "disabled":
            return
        self._decode_32_byte_key(self.storage_signing_key.get_secret_value(), "STORAGE_SIGNING_KEY")
        self._decode_32_byte_key(
            self.attachment_object_key_hmac_key.get_secret_value(),
            "ATTACHMENT_OBJECT_KEY_HMAC_KEY",
        )
        if self.app_env not in {"local", "test"} and self.storage_backend == "synthetic":
            raise ValueError("STORAGE_BACKEND synthetic is limited to local and test")
        if self.app_env not in {"local", "test"} and (
            self.storage_signing_key.get_secret_value() == DEFAULT_STORAGE_SIGNING_KEY
            or self.attachment_object_key_hmac_key.get_secret_value()
            == DEFAULT_ATTACHMENT_OBJECT_KEY_HMAC_KEY
        ):
            raise ValueError("deployed storage keys must not use local defaults")
        if (
            self.storage_signing_key.get_secret_value()
            == self.attachment_object_key_hmac_key.get_secret_value()
        ):
            raise ValueError("storage signing and attachment object keys must differ")
        if self.storage_backend == "synthetic":
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

    def decoded_storage_signing_key(self) -> bytes:
        return self._decode_32_byte_key(
            self.storage_signing_key.get_secret_value(), "STORAGE_SIGNING_KEY"
        )

    def decoded_attachment_object_key_hmac_key(self) -> bytes:
        return self._decode_32_byte_key(
            self.attachment_object_key_hmac_key.get_secret_value(),
            "ATTACHMENT_OBJECT_KEY_HMAC_KEY",
        )

    def _validate_scanner_settings(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", self.malware_scanner_definition):
            raise ValueError("MALWARE_SCANNER_DEFINITION is invalid")
        if self.malware_scanner_backend == "disabled":
            return
        if self.app_env not in {"local", "test"}:
            raise ValueError("MALWARE_SCANNER_BACKEND synthetic is limited to local and test")
        self._decode_32_byte_key(
            self.malware_scanner_signing_key.get_secret_value(),
            "MALWARE_SCANNER_SIGNING_KEY",
        )

    def decoded_malware_scanner_signing_key(self) -> bytes:
        return self._decode_32_byte_key(
            self.malware_scanner_signing_key.get_secret_value(),
            "MALWARE_SCANNER_SIGNING_KEY",
        )

    @property
    def cors_allowed_origins(self) -> tuple[str, ...]:
        if self.app_env in {"local", "test"}:
            return ("http://127.0.0.1:5174",)
        return (str(self.frontend_url).rstrip("/"),)
