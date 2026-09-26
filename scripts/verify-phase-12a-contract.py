from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "docs" / "migration" / "phase-12"

DOCUMENTS = {
    "plan": PHASE / "SUBPHASE_PLAN.md",
    "inventory": PHASE / "PART_12A_DEPENDENCY_INVENTORY.md",
    "contract": PHASE / "PART_12A_OUTPUT_AND_DELIVERY_CONTRACT.md",
    "golden": PHASE / "PART_12A_GOLDEN_CASES.md",
    "amendment": PHASE / "PART_12A_AMENDMENT_PROPOSAL.md",
    "completion": PHASE / "PART_12A_COMPLETION.md",
}

EXPECTED_CATALOGUE = {
    *(f"P12-NOT-{index:02d}" for index in range(1, 15)),
    *(f"P12-TSK-{index:02d}" for index in range(1, 18)),
    *(f"P12-DSH-{index:02d}" for index in range(1, 13)),
    *(f"P12-RPT-{index:02d}" for index in range(1, 20)),
    *(f"P12-OUT-{index:02d}" for index in range(1, 19)),
    *(f"P12-DB-{index:02d}" for index in range(1, 10)),
    *(f"P12-IND-{index:02d}" for index in range(1, 9)),
}

EXPECTED_UPSTREAM = {
    "P0-NOTIFICATION-BELL",
    "P0-GENERATED-NOTIFICATIONS",
    "P0-TASK-CENTER",
    "P0-ADMIN-DASHBOARD",
    "P0-CLINICAL-DASHBOARD",
    "P0-REPORTS-EXPORTS",
    "P0-PAYSLIP-FILE",
    "P0-SIF-FILE",
    "P0-REPORT-FILES",
    "P0-TASK-ACCEPTANCE",
    "phase8a-admin-leave-screen",
    "phase8a-notification-producer",
    "phase8a-balance-csv",
    "phase8a-notifications",
    "phase8a-tasks",
    "phase8a-dashboards-reports",
    "UI-01",
    "UI-09",
    "UI-10",
    "UI-11",
    "UI-12",
    "UI-13",
    "UI-16",
    "JS-15",
    "JS-17",
    "JS-18",
    "JS-19",
    "JS-20",
    "EXT-04",
    "EXT-05",
    "EXT-06",
    "EXT-07",
    "EXT-08",
    "ATT-UI-01",
    "ATT-UI-03",
    "ATT-UI-08",
    "ATT-UI-09",
    "ATT-UI-12",
    "ATT-UI-13",
    "ATT-EXT-04",
    "P11-INS-02",
    "P11-AST-03",
    "P11-REQ-02",
    "P11-REQ-03",
    "P11-REQ-04",
    "P11-OFF-02",
    "P11-OFF-03",
    "P11-OFF-05",
    "P11-LTR-01",
    "P11-LTR-02",
    "P11-LTR-03",
    "P11-LTR-04",
}

REQUIRED_SOURCE_MARKERS = {
    "src/notificationApi.js": ["readNotifications", "readUnreadCount", "markNotificationRead"],
    "src/taskApi.js": ["parseTaskCatalogue", "readTasks", "/api/v1/tasks"],
    "src/dashboardApi.js": ["parseDashboard", "readDashboard", "/api/v1/dashboards/"],
    "src/reportApi.js": ["readReport", "downloadReportCsv", "/api/v1/reports/"],
    "src/renderedOutputApi.js": ["downloadReportPdf", "downloadSelfPayslipPdf", "downloadPayslipsZip"],
    "src/outputDelivery.js": ["saveDownload", "openPdf", "createObjectURL"],
    "src/NotificationBell.jsx": ["readNotifications", "markAllNotificationsRead"],
    "src/Tasks.jsx": ["readTasks", "mergePage"],
    "src/Dashboards.jsx": ["readDashboard"],
    "src/Reports.jsx": ["downloadReportCsv", "downloadReportPdf"],
}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def text(name: str) -> str:
    path = DOCUMENTS[name]
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def assert_exact_ids(body: str, pattern: str, expected: set[str], label: str) -> None:
    found = re.findall(pattern, body)
    duplicates = sorted({item for item in found if found.count(item) > 1})
    if duplicates:
        fail(f"duplicate {label}: {', '.join(duplicates)}")
    actual = set(found)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        fail(f"{label} mismatch; missing={missing}, extra={extra}")


def main() -> None:
    bodies = {name: text(name) for name in DOCUMENTS}
    inventory = bodies["inventory"]
    contract = bodies["contract"]
    golden = bodies["golden"]
    plan = bodies["plan"]
    amendment = bodies["amendment"]

    assert_exact_ids(inventory, r"\| `(P12-(?:NOT|TSK|DSH|RPT|OUT|DB|IND)-\d{2})` \|", EXPECTED_CATALOGUE, "catalogue IDs")
    assert_exact_ids(
        inventory,
        r"\| `(P0-[A-Z-]+|P11-[A-Z]+-\d{2}|phase8a-[a-z-]+|UI-\d{2}|JS-\d{2}|EXT-\d{2}|ATT-(?:UI|EXT)-\d{2})` \|",
        EXPECTED_UPSTREAM,
        "upstream assignments",
    )

    for line in inventory.splitlines():
        if re.match(r"\| `P12-(?:NOT|TSK|DSH|RPT|OUT|DB|IND)-\d{2}` \|", line):
            owner_cell = line.split("|")[-2].strip()
            owners = re.findall(r"^(?:12[B-G]|13)$", owner_cell)
            if len(owners) != 1:
                fail(f"catalogue row must name one owner: {line}")

    expected_cases = {f"12A-GC-{index:03d}" for index in range(1, 51)}
    assert_exact_ids(golden, r"\| `(12A-GC-\d{3})` \|", expected_cases, "golden cases")

    for part in "ABCDEFGH":
        if f"| 12{part} |" not in plan:
            fail(f"subphase plan does not assign Part 12{part}")

    contract_tokens = [
        "Asia/Dubai",
        "ROUND_HALF_UP",
        "UTF-8",
        "CRLF",
        "Content-Disposition",
        "application/problem+json",
        "Idempotency-Key",
        "sourceDigest",
        "nextCursor",
        "Cache-Control: no-store",
        "X-Content-Type-Options: nosniff",
        "deterministic bytes",
        "Phase 13",
    ]
    for token in contract_tokens:
        if token not in contract:
            fail(f"contract is missing {token!r}")

    if "No new table or column is required" not in amendment:
        fail("amendment decision must state the schema result")
    for token in ["append_phase12_output_audit", "workloop_runtime", "REVOKE ALL", "SECURITY DEFINER"]:
        if token not in amendment:
            fail(f"amendment proposal is missing {token!r}")

    for source, markers in REQUIRED_SOURCE_MARKERS.items():
        path = ROOT / source
        if not path.is_file():
            fail(f"catalogued source is missing: {source}")
        source_text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in source_text:
                fail(f"source marker {marker!r} is missing from {source}")
    for retired in (
        "src/utils/notificationStorage.js",
        "src/utils/taskStorage.js",
        "src/utils/reportUtils.js",
        "src/utils/payslipGenerator.js",
        "src/utils/sifGenerator.js",
        "src/utils/letterTemplates.js",
    ):
        if (ROOT / retired).exists():
            fail(f"retired source was restored: {retired}")

    prohibited = ["email delivery", "SMS delivery", "push delivery", "production credential", "cloud scheduler"]
    for item in prohibited:
        if f"Not authorized: {item}" not in plan:
            fail(f"plan is missing the prohibition for {item}")

    print(
        "Phase 12A contract verification passed: "
        f"{len(EXPECTED_CATALOGUE)} catalogue entries, "
        f"{len(EXPECTED_UPSTREAM)} upstream assignments, 50 golden cases."
    )


if __name__ == "__main__":
    try:
        main()
    except UnicodeDecodeError as exc:
        fail(f"UTF-8 decode failure: {exc}")
    except OSError as exc:
        fail(str(exc))
    sys.exit(0)
