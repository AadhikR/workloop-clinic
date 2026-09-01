from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KCADM_CONFIG = "/tmp/workloop-phase-3d-kcadm.config"
MAPPER_NAME = "access-token-subject"


def docker_path() -> str:
    configured = os.environ.get("DOCKER")
    if configured:
        return configured
    found = shutil.which("docker")
    if found:
        return found
    windows_path = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
    if windows_path.exists():
        return str(windows_path)
    raise RuntimeError("Docker executable not found")


DOCKER_COMPOSE = [docker_path(), "compose"]


def run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*DOCKER_COMPOSE, *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        input=input_text,
    )


def kcadm_json(*args: str) -> Any:
    result = run(
        "exec",
        "-T",
        "keycloak",
        "/opt/keycloak/bin/kcadm.sh",
        *args,
        "--config",
        KCADM_CONFIG,
    )
    return json.loads(result.stdout)


def configure_subject_mapper() -> None:
    clients = kcadm_json(
        "get", "clients", "-r", "workloop-dev", "-q", "clientId=workloop-migration-web"
    )
    if not isinstance(clients, list) or len(clients) != 1:
        raise RuntimeError("Expected one Workloop migration web client")
    client_id = clients[0].get("id")
    if not isinstance(client_id, str) or not client_id:
        raise RuntimeError("Workloop migration web client has no identifier")

    mappers = kcadm_json(
        "get", f"clients/{client_id}/protocol-mappers/models", "-r", "workloop-dev"
    )
    matching = [mapper for mapper in mappers if mapper.get("name") == MAPPER_NAME]
    if matching:
        if len(matching) != 1:
            raise RuntimeError("Access-token subject mapper is duplicated")
        mapper = matching[0]
        config = mapper.get("config", {})
        if (
            mapper.get("protocol") != "openid-connect"
            or mapper.get("protocolMapper") != "oidc-sub-mapper"
            or config.get("access.token.claim") != "true"
            or config.get("introspection.token.claim") != "true"
        ):
            raise RuntimeError(
                "Access-token subject mapper does not match the approved configuration"
            )
        return

    payload = json.dumps(
        {
            "name": MAPPER_NAME,
            "protocol": "openid-connect",
            "protocolMapper": "oidc-sub-mapper",
            "config": {
                "access.token.claim": "true",
                "introspection.token.claim": "true",
            },
        }
    )
    run(
        "exec",
        "-T",
        "keycloak",
        "/opt/keycloak/bin/kcadm.sh",
        "create",
        f"clients/{client_id}/protocol-mappers/models",
        "-r",
        "workloop-dev",
        "--config",
        KCADM_CONFIG,
        "-f",
        "-",
        input_text=payload,
    )


def main() -> None:
    try:
        run(
            "exec",
            "-T",
            "keycloak",
            "sh",
            "-c",
            "/opt/keycloak/bin/kcadm.sh config credentials "
            f"--config {KCADM_CONFIG} --server http://127.0.0.1:8080 --realm master "
            '--user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" '
            ">/dev/null 2>&1",
        )
        configure_subject_mapper()
    finally:
        subprocess.run(
            [*DOCKER_COMPOSE, "exec", "-T", "keycloak", "rm", "-f", KCADM_CONFIG],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [*DOCKER_COMPOSE, "exec", "-T", "keycloak", "test", "!", "-e", KCADM_CONFIG],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    print("Phase 3D Keycloak configuration is ready")


if __name__ == "__main__":
    try:
        main()
    except (json.JSONDecodeError, RuntimeError, subprocess.CalledProcessError) as error:
        detail = str(error) or error.__class__.__name__
        print(f"Phase 3D Keycloak configuration failed: {detail}", file=sys.stderr)
        raise SystemExit(1) from error
