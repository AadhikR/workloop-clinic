from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "infra" / "digitalocean" / "main.tf"
PACKAGE = ROOT / "package.json"
REALM = ROOT / "keycloak" / "cloud" / "workloop-dev-realm.json"
DOCKERFILE = ROOT / "keycloak" / "Dockerfile"
MFA_GATE = ROOT / "keycloak" / "cloud" / "arm-admin-totp.sh"


def require(source: str, value: str, description: str) -> None:
    if value not in source:
        raise AssertionError(f"missing {description}")


def walk_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in walk_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in walk_values(child)]
    return [value] if isinstance(value, str) else []


def verify_terraform() -> None:
    source = TERRAFORM.read_text(encoding="utf-8")
    for value, description in (
        ("budget_ceiling_usd == 20", "fixed budget guard"),
        ("var.test_window_hours <= 72", "72-hour window guard"),
        ("enabled = !var.public_exposure_enabled", "maintenance-mode gate"),
        (
            "!var.public_exposure_enabled || var.admin_mfa_gate_armed",
            "administrator MFA gate",
        ),
        ('size                 = "db-s-1vcpu-1gb"', "smallest approved database"),
        ('instance_size_slug = "apps-s-1vcpu-2gb"', "Keycloak memory allocation"),
        ('permission = "readwrite"', "bucket-scoped application key"),
        ('acl           = "private"', "private Space"),
        (
            "digitalocean_database_cluster.proof[0].urn",
            "database project assignment",
        ),
        ("digitalocean_app.proof[0].urn", "application project assignment"),
        (
            'value = "$${workloop-runtime.DATABASE_PRIVATE_URL}"',
            "private API database URL",
        ),
        ('dockerfile_path    = "keycloak/Dockerfile"', "Keycloak Dockerfile path"),
        ("deploy_on_push = false", "manual deployment control"),
    ):
        require(source, value, description)
    if source.count('dockerfile_path    = "backend/Dockerfile"') != 2:
        raise AssertionError(
            "the API and migration job must use the repository-root backend Dockerfile path"
        )
    if source.count("ignore_changes = [settings]") != 3:
        raise AssertionError(
            "all PostgreSQL users must ignore provider-only database settings drift"
        )
    forbidden = (
        "public-read",
        'permission = "fullaccess"',
        "DEDICATED_IP",
        "deploy_on_push = true",
        "storage_autoscale",
        'dockerfile_path    = "Dockerfile"',
    )
    for value in forbidden:
        if value in source:
            raise AssertionError(f"forbidden Terraform setting: {value}")


def verify_realm() -> None:
    realm = json.loads(REALM.read_text(encoding="utf-8"))
    if realm.get("smtpServer") != {}:
        raise AssertionError("cloud realm must not configure SMTP")
    values = walk_values(realm)
    if any("*" in value for value in values):
        raise AssertionError(
            "cloud realm must not contain wildcard callbacks or origins"
        )
    clients = {client["clientId"]: client for client in realm["clients"]}
    migration_client = clients["workloop-migration-web"]
    if migration_client["redirectUris"] != ["${WORKLOOP_PUBLIC_URL}/auth/callback"]:
        raise AssertionError("cloud callback is not exact")
    if migration_client["webOrigins"] != ["${WORKLOOP_PUBLIC_URL}"]:
        raise AssertionError("cloud web origin is not exact")
    users = realm.get("users", [])
    if len(users) != 1 or users[0].get("username") != "phase-6g-admin-test":
        raise AssertionError("cloud realm must contain one named synthetic identity")
    credentials = users[0].get("credentials")
    if not isinstance(credentials, list) or credentials[0].get("value") != (
        "${WORKLOOP_SYNTHETIC_USER_PASSWORD}"
    ):
        raise AssertionError(
            "synthetic credential must remain an environment placeholder"
        )


def verify_frontend_build_toolchain() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    if package.get("engines") != {"node": "24.11.1", "npm": "11.6.2"}:
        raise AssertionError("cloud frontend build toolchain must match GitHub Actions")


def verify_keycloak_image() -> None:
    source = DOCKERFILE.read_text(encoding="utf-8")
    require(source, "quay.io/keycloak/keycloak:26.7.3@sha256:", "pinned Keycloak image")
    require(source, "/opt/keycloak/bin/kc.sh build", "optimized Keycloak build")
    require(source, "KC_HTTP_RELATIVE_PATH=/auth", "built Keycloak public path")
    require(source, "KC_HTTP_MANAGEMENT_RELATIVE_PATH=/management", "built management path")
    require(source, '"start", "--optimized"', "production Keycloak start")
    require(source, "arm-admin-totp.sh", "administrator MFA helper")
    if "start-dev" in source or ":latest" in source:
        raise AssertionError(
            "Keycloak production image must not use development or floating tags"
        )

    gate = MFA_GATE.read_text(encoding="utf-8")
    require(gate, "CONFIGURE_TOTP", "administrator TOTP required action")
    require(gate, "Password-only administrator access still succeeds", "MFA refusal check")
    if "set -eu" not in gate or "trap 'rm -f" not in gate:
        raise AssertionError("administrator MFA helper must fail closed and remove temporary files")


def main() -> int:
    verify_terraform()
    verify_realm()
    verify_frontend_build_toolchain()
    verify_keycloak_image()
    print("Phase 6G static cloud boundaries are ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
