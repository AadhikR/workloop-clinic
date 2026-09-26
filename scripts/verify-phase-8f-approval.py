from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    content = (ROOT / path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in content]
    if missing:
        raise SystemExit(f"{path} is missing Phase 8F contract tokens: {missing}")


def main() -> None:
    require(
        "backend/app/leave_approval_api.py",
        'operation_id="decide_leave_as_approver"',
        'operation_id="decide_leave_as_admin"',
        'operation_id="create_leave_delegation"',
        'operation_id="update_leave_delegation"',
        'operation_id="delete_leave_delegation"',
        "parse_idempotency_key(request, required=True)",
    )
    require(
        "backend/app/services/leave_approval.py",
        '"directReport"',
        '"activeDelegation"',
        '"ManagerApproved"',
        '"ManagerRejected"',
        '"Approved"',
        '"Rejected"',
        'raise ServiceExecutionError("state_conflict")',
    )
    require(
        "backend/app/repositories/leave_approval.py",
        "lock_leave_decision_authority",
        "append_leave_domain_decision_audit",
        "read_leave_audit_projection",
    )
    require(
        "backend/alembic/versions/e8f4c7b2a610_add_phase8f_leave_approval_authority.py",
        'revision: str = "e8f4c7b2a610"',
        'down_revision: str | Sequence[str] | None = "d1e5f8a2c904"',
        "leave_decision_visibility",
        "lock_leave_decision_authority",
        "append_leave_domain_decision_audit",
        "read_leave_audit_projection",
    )
    require(
        "src/leaveApprovalApi.js",
        "/api/v1/leave/approvals/queue",
        "/api/v1/leave/approvals/branch",
        "/api/v1/leave/delegations/branch",
        "Idempotency-Key",
    )
    if (ROOT / "src/utils/leaveStorage.js").exists():
        raise SystemExit("retired leave storage source was restored")
    if (ROOT / "tests/phase-8f-legacy-freeze.test.js").exists():
        raise SystemExit("retired Phase 8F legacy freeze test was restored")

    cutover_path = ROOT / "docs/migration/phase-8/cutover/leave-approval-workflows.json"
    cutover = json.loads(cutover_path.read_text(encoding="utf-8"))
    if cutover["authority"] != {
        "readSystem": "migration-fastapi",
        "writeSystem": "migration-fastapi",
        "writableSystems": ["migration-fastapi"],
    }:
        raise SystemExit("approval cutover does not name migration-fastapi as sole authority")
    if cutover["status"]["current"] != "completed":
        raise SystemExit("approval cutover is not complete")

    print("Phase 8F approval contract check passed")


if __name__ == "__main__":
    main()
