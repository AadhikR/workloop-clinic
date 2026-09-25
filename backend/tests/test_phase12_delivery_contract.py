import uuid
from datetime import UTC, date, datetime

from app.schemas.dashboards import DashboardCard, DashboardResponse
from app.schemas.reports import ReportColumn, ReportResponse, ReportTotals
from app.schemas.tasks import TaskCategory, TaskItem, TaskListResponse, TaskNavigation

PRECISE_NOW = datetime(2026, 9, 25, 8, 0, 0, 123456, tzinfo=UTC)
SOURCE_VERSION = "sha256:" + "a" * 64
ENTITY_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def test_phase12_read_timestamps_serialize_to_contract_milliseconds() -> None:
    task = TaskItem(
        id="leave:00000000-0000-4000-8000-000000000001",
        entity="leave_request",
        entity_id=ENTITY_ID,
        title="Review leave",
        subtitle="Synthetic task",
        urgency="action",
        due_date=None,
        created_at=PRECISE_NOW,
        navigation=TaskNavigation(screen="leave"),
    )
    tasks = TaskListResponse(
        categories=[TaskCategory(code="leave", label="Leave", status="ok", count=1, items=[task])],
        next_cursor=None,
        as_of=PRECISE_NOW,
        source_version=SOURCE_VERSION,
    ).model_dump(mode="json", by_alias=True)
    dashboard = DashboardResponse(
        as_of=PRECISE_NOW,
        business_date=date(2026, 9, 25),
        source_version=SOURCE_VERSION,
        cards=[
            DashboardCard(
                code="headcount",
                label="Headcount",
                value=1,
                unit="people",
                severity="info",
            )
        ],
    ).model_dump(mode="json", by_alias=True)
    report = ReportResponse(
        report_id="headcount",
        columns=[ReportColumn(key="employees", label="Employees", type="integer")],
        rows=[{"employees": 1}],
        totals=ReportTotals(row_count=1),
        filters={},
        as_of=PRECISE_NOW,
        source_version=SOURCE_VERSION,
    ).model_dump(mode="json", by_alias=True)

    assert tasks["asOf"] == "2026-09-25T08:00:00.123Z"
    assert tasks["categories"][0]["items"][0]["createdAt"] == "2026-09-25T08:00:00.123Z"
    assert dashboard["asOf"] == "2026-09-25T08:00:00.123Z"
    assert report["asOf"] == "2026-09-25T08:00:00.123Z"
