import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from app.storage.worker_settings import StorageWorkerSettings


def set_worker_environment(monkeypatch: MonkeyPatch) -> None:
    values = {
        "WORKLOOP_ENVIRONMENT": "shared-development",
        "WORKLOOP_DATA_CLASS": "synthetic-only",
        "DATABASE_URL": "postgresql+psycopg://worker:test-secret@postgres/workloop",
        "STORAGE_BACKEND": "spaces",
        "SPACES_ENDPOINT_URL": "https://fra1.digitaloceanspaces.com",
        "SPACES_REGION": "fra1",
        "SPACES_BUCKET": "workloop-clinic-dev-example",
        "SPACES_ACCESS_KEY": "scoped-access",
        "SPACES_SECRET_KEY": "scoped-secret",
        "MALWARE_SCANNER_BACKEND": "synthetic",
        "MALWARE_SCANNER_SIGNING_KEY": "NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    for name in (
        "APP_ENV",
        "FRONTEND_URL",
        "CURSOR_SIGNING_KEY",
        "OIDC_ISSUER",
        "OIDC_AUDIENCE",
        "OIDC_JWKS_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_storage_worker_settings_do_not_require_api_configuration(
    monkeypatch: MonkeyPatch,
) -> None:
    set_worker_environment(monkeypatch)

    settings = StorageWorkerSettings()  # pyright: ignore[reportCallIssue]

    assert settings.storage_backend == "spaces"
    assert settings.malware_scanner_backend == "synthetic"
    assert "test-secret" not in repr(settings)
    assert "scoped-secret" not in repr(settings)


@pytest.mark.parametrize("environment", ["development", "staging", "production"])
def test_storage_worker_settings_reject_synthetic_scanner_outside_shared_development(
    monkeypatch: MonkeyPatch,
    environment: str,
) -> None:
    set_worker_environment(monkeypatch)
    monkeypatch.setenv("WORKLOOP_ENVIRONMENT", environment)

    with pytest.raises(ValidationError, match="synthetic-only shared development"):
        StorageWorkerSettings()  # pyright: ignore[reportCallIssue]


def test_storage_worker_settings_require_scoped_shared_development_scanner_key(
    monkeypatch: MonkeyPatch,
) -> None:
    set_worker_environment(monkeypatch)
    monkeypatch.delenv("MALWARE_SCANNER_SIGNING_KEY")

    with pytest.raises(ValidationError, match="must not use the local default"):
        StorageWorkerSettings()  # pyright: ignore[reportCallIssue]
