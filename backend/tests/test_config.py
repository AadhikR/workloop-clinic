import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from app.core.config import Settings


def set_required_environment(monkeypatch: MonkeyPatch) -> None:
    values = {
        "APP_ENV": "test",
        "APP_BASE_URL": "http://127.0.0.1:8000",
        "FRONTEND_URL": "http://127.0.0.1:5174",
        "LOG_LEVEL": "INFO",
        "DATABASE_HEALTH_TIMEOUT_SECONDS": "5",
        "APPLICATION_USER_LOOKUP_TIMEOUT_SECONDS": "5",
        "AUTHORIZATION_CONTEXT_SETUP_TIMEOUT_SECONDS": "5",
        "OIDC_ISSUER": "http://127.0.0.1:8080/realms/workloop-dev",
        "OIDC_AUDIENCE": "workloop-api",
        "OIDC_JWKS_URL": (
            "http://127.0.0.1:8080/realms/workloop-dev/protocol/openid-connect/certs"
        ),
        "OIDC_JWKS_CONNECT_TIMEOUT_SECONDS": "2",
        "OIDC_JWKS_READ_TIMEOUT_SECONDS": "2",
        "OIDC_JWKS_TOTAL_TIMEOUT_SECONDS": "5",
        "OIDC_JWKS_CACHE_TTL_SECONDS": "300",
        "OIDC_JWKS_REFRESH_COOLDOWN_SECONDS": "1",
        "DATABASE_URL": "postgresql+psycopg://workloop_runtime:test-secret@postgres/workloop",
        "CURSOR_SIGNING_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA",
        "IDEMPOTENCY_RECOVERY_CURRENT_KEY_ID": "1234abcd",
        "IDEMPOTENCY_RECOVERY_CURRENT_KEY": "MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTE",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_settings_hide_database_url(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert "test-secret" not in repr(settings)
    assert "MDAwMDAwMDAw" not in repr(settings)


@pytest.mark.parametrize(
    "value",
    ["short", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="],
)
def test_settings_require_a_32_byte_unpadded_cursor_key(
    monkeypatch: MonkeyPatch, value: str
) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("CURSOR_SIGNING_KEY", value)

    with pytest.raises(ValidationError, match="CURSOR_SIGNING_KEY"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_settings_validate_recovery_key_rotation(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv(
        "IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS",
        '[{"keyId":"8765dcba","key":"MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjI",'
        '"acceptUntil":"2026-09-17T00:00:00Z"}]',
    )

    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert settings.decoded_previous_idempotency_recovery_keys()[0][0] == "8765dcba"


@pytest.mark.parametrize(
    "previous",
    [
        '[{"keyId":"1234abcd","key":"MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjI",'
        '"acceptUntil":"2026-09-17T00:00:00Z"}]',
        '[{"keyId":"8765dcba","key":"short","acceptUntil":"2026-09-17T00:00:00Z"}]',
        '[{"keyId":"8765dcba","key":"MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjI",'
        '"acceptUntil":"2026-09-17T04:00:00+04:00"}]',
    ],
)
def test_settings_reject_invalid_recovery_rotation(monkeypatch: MonkeyPatch, previous: str) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS", previous)

    with pytest.raises(ValidationError, match="IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_settings_reject_non_postgresql_database(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///workloop.db")

    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_settings_reject_unbounded_application_user_lookup(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("APPLICATION_USER_LOOKUP_TIMEOUT_SECONDS", "31")

    with pytest.raises(ValidationError, match="APPLICATION_USER_LOOKUP_TIMEOUT_SECONDS"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_settings_reject_unbounded_authorization_context_setup(
    monkeypatch: MonkeyPatch,
) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("AUTHORIZATION_CONTEXT_SETUP_TIMEOUT_SECONDS", "31")

    with pytest.raises(ValidationError, match="AUTHORIZATION_CONTEXT_SETUP_TIMEOUT_SECONDS"):
        Settings()  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize("app_env", ["development", "staging", "production"])
def test_deployed_settings_require_https_oidc_urls(monkeypatch: MonkeyPatch, app_env: str) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", app_env)

    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_deployed_settings_accept_https_oidc_urls(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.test/realms/workloop")
    monkeypatch.setenv(
        "OIDC_JWKS_URL", "https://identity.example.test/realms/workloop/openid-connect/certs"
    )
    monkeypatch.setenv("APP_BASE_URL", "https://workloop.example.test")
    monkeypatch.setenv("FRONTEND_URL", "https://workloop.example.test")
    monkeypatch.setenv("TRUSTED_PROXY", "digitalocean_app_platform")

    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert settings.oidc_issuer.scheme == "https"


def test_settings_reject_oidc_url_credentials(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv(
        "OIDC_JWKS_URL",
        "http://user:password@127.0.0.1:8080/realms/workloop-dev/certs",
    )

    with pytest.raises(ValidationError, match="must not contain credentials"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_local_settings_require_exact_migration_frontend(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5174")

    with pytest.raises(ValidationError, match="FRONTEND_URL"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_cloud_cors_allowlist_uses_exact_frontend_origin(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OIDC_ISSUER", "https://identity.example.test/realms/workloop")
    monkeypatch.setenv(
        "OIDC_JWKS_URL", "https://identity.example.test/realms/workloop/openid-connect/certs"
    )
    monkeypatch.setenv("APP_BASE_URL", "https://workloop.example.test")
    monkeypatch.setenv("FRONTEND_URL", "https://workloop.example.test")
    monkeypatch.setenv("TRUSTED_PROXY", "digitalocean_app_platform")

    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert settings.cors_allowed_origins == ("https://workloop.example.test",)


def test_deployed_settings_require_named_proxy(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_BASE_URL", "https://workloop.example.test")
    monkeypatch.setenv("FRONTEND_URL", "https://workloop.example.test")
    monkeypatch.setenv("OIDC_ISSUER", "https://workloop.example.test/auth/realms/workloop-dev")
    monkeypatch.setenv(
        "OIDC_JWKS_URL",
        "https://workloop.example.test/auth/realms/workloop-dev/protocol/openid-connect/certs",
    )

    with pytest.raises(ValidationError, match="TRUSTED_PROXY"):
        Settings()  # pyright: ignore[reportCallIssue]


def test_spaces_settings_require_exact_https_regional_endpoint(monkeypatch: MonkeyPatch) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "spaces")
    monkeypatch.setenv("SPACES_ENDPOINT_URL", "https://fra1.digitaloceanspaces.com")
    monkeypatch.setenv("SPACES_REGION", "fra1")
    monkeypatch.setenv("SPACES_BUCKET", "workloop-phase-6g-example")
    monkeypatch.setenv("SPACES_ACCESS_KEY", "scoped-access")
    monkeypatch.setenv("SPACES_SECRET_KEY", "scoped-secret")

    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert settings.storage_backend == "spaces"
    assert "scoped-secret" not in repr(settings)

    monkeypatch.setenv("SPACES_ENDPOINT_URL", "https://ams3.digitaloceanspaces.com")
    with pytest.raises(ValidationError, match="must match SPACES_REGION"):
        Settings()  # pyright: ignore[reportCallIssue]


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DATABASE_HEALTH_TIMEOUT_SECONDS", "5.1"),
        ("API_REQUEST_TIMEOUT_SECONDS", "15.1"),
    ],
)
def test_settings_reject_deadlines_above_contract(
    monkeypatch: MonkeyPatch, name: str, value: str
) -> None:
    set_required_environment(monkeypatch)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match=name):
        Settings()  # pyright: ignore[reportCallIssue]
