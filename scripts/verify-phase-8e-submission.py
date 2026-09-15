from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path} is missing Phase 8E contract tokens: {missing}")


def main() -> None:
    require(
        "backend/app/leave_request_api.py",
        'operation_id="submit_employee_leave_request"',
        'operation_id="submit_admin_leave_request"',
        'operation_id="cancel_employee_leave_request"',
        'operation_id="cancel_admin_leave_request"',
        "parse_idempotency_key(request, required=True)",
    )
    require(
        "backend/app/services/leave_request.py",
        "leave_request_submitted",
        "leave_request_auto_approved",
        "leave_request_cancelled",
    )
    require(
        "backend/app/repositories/leave_request.py",
        "Auto-approved by leave type policy",
        "pg_advisory_xact_lock",
    )
    require(
        "backend/alembic/versions/d1e5f8a2c904_add_phase8e_leave_request_audit.py",
        'revision: str = "d1e5f8a2c904"',
        'down_revision: str | Sequence[str] | None = "a83d5e7c1b29"',
        "_append_audit_event_phase8e_prior",
        "leave_request_submitted",
        "leave_request_auto_approved",
        "leave_request_cancelled",
    )
    require(
        "migration/src/leaveRequestApi.js",
        "/api/v1/leave/requests/self",
        "/api/v1/leave/requests/branch",
        "/cancel/self",
        "/cancel/branch",
        "Idempotency-Key",
    )
    require(
        "tests/phase-8e-legacy-freeze.test.js",
        "employee_submit_leave_request",
        "employee_cancel_leave_request",
    )

    cutover_path = ROOT / "docs/migration/phase-8/cutover/leave-request-submission.json"
    cutover = json.loads(cutover_path.read_text(encoding="utf-8"))
    if cutover["authority"] != {
        "readSystem": "migration-fastapi",
        "writeSystem": "migration-fastapi",
        "writableSystems": ["migration-fastapi"],
    }:
        raise SystemExit("submission cutover does not name migration-fastapi as sole authority")
    if cutover["status"]["current"] != "completed":
        raise SystemExit("submission cutover is not complete")

    print("Phase 8E submission contract check passed")


if __name__ == "__main__":
    main()
