from __future__ import annotations

import json
import uuid
from datetime import date

import pytest

import app.expiry_command as expiry_command
from app.expiry_command import _candidate  # pyright: ignore[reportPrivateUsage]

SOURCE = uuid.UUID("b4000000-0000-4000-8000-000000000001")
BUSINESS_DATE = date(2026, 9, 24)


def test_expiry_candidate_requires_an_exact_threshold() -> None:
    due = _candidate(
        SOURCE,
        "document",
        date(2026, 10, 24),
        BUSINESS_DATE,
        (60, 30, 14),
        "employee_document",
        "document_expiry",
        "Document expiring",
    )
    assert due is not None
    assert due.threshold == 30
    assert (
        _candidate(
            SOURCE,
            "document",
            date(2026, 10, 23),
            BUSINESS_DATE,
            (60, 30, 14),
            "employee_document",
            "document_expiry",
            "Document expiring",
        )
        is None
    )


def test_expiry_candidate_rejects_expired_and_missing_dates() -> None:
    values = (None, date(2026, 9, 23), BUSINESS_DATE)
    for source_date in values:
        assert (
            _candidate(
                SOURCE,
                "clinical",
                source_date,
                BUSINESS_DATE,
                (90, 30, 14),
                "employee_document",
                "clinical_credential_expiry",
                "Clinical credential expiring",
            )
            is None
        )


def test_expiry_command_failure_has_safe_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def fail(*_values: object, **_named: object) -> int:
        raise RuntimeError("sensitive database detail")

    monkeypatch.setattr(expiry_command, "run_expiry", fail)
    monkeypatch.setenv("EXPIRY_DATABASE_URL", "postgresql://not-logged")
    monkeypatch.setenv("WORKLOOP_EXPIRY_PROCESSING_ENABLED", "true")
    monkeypatch.setattr(
        "sys.argv",
        [
            "expiry_command",
            "--company-id",
            "b4000000-0000-4000-8000-000000000002",
            "--branch-id",
            "b4000000-0000-4000-8000-000000000003",
            "--business-date",
            "2026-09-24",
        ],
    )

    with pytest.raises(SystemExit, match="1"):
        expiry_command.main()

    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == '{"error":"expiry_processing_failed"}\n'
    assert "sensitive" not in output.err


def test_expiry_command_stays_disabled_before_promotion(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EXPIRY_DATABASE_URL", "postgresql://not-used")
    monkeypatch.delenv("WORKLOOP_EXPIRY_PROCESSING_ENABLED", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "expiry_command",
            "--company-id",
            "b4000000-0000-4000-8000-000000000002",
            "--tenant-wide",
            "--business-date",
            "2026-09-24",
        ],
    )

    with pytest.raises(SystemExit, match="1"):
        expiry_command.main()

    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == '{"error":"expiry_processing_disabled"}\n'


def test_expiry_command_processes_each_approved_scope(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    company = "b4000000-0000-4000-8000-000000000002"
    branch = "b4000000-0000-4000-8000-000000000003"
    calls: list[tuple[uuid.UUID, uuid.UUID | None, date]] = []

    async def record_scope(
        _database_url: str,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        business_date: date,
    ) -> int:
        calls.append((company_id, branch_id, business_date))
        return 2

    monkeypatch.setattr(expiry_command, "run_expiry", record_scope)
    monkeypatch.setenv("EXPIRY_DATABASE_URL", "postgresql://not-logged")
    monkeypatch.setenv("WORKLOOP_EXPIRY_PROCESSING_ENABLED", "true")
    monkeypatch.setenv("WORKLOOP_EXPIRY_BUSINESS_DATE", "2026-09-24")
    monkeypatch.setenv(
        "WORKLOOP_EXPIRY_SCOPES_JSON",
        json.dumps(
            [
                {"company_id": company, "branch_id": branch},
                {"company_id": company, "branch_id": None},
            ]
        ),
    )
    monkeypatch.setattr("sys.argv", ["expiry_command"])

    expiry_command.main()

    assert calls == [
        (uuid.UUID(company), uuid.UUID(branch), BUSINESS_DATE),
        (uuid.UUID(company), None, BUSINESS_DATE),
    ]
    output = json.loads(capsys.readouterr().out)
    assert output == {
        "business_date": "2026-09-24",
        "inserted": 4,
        "scopes": [
            {"branch_id": branch, "company_id": company},
            {"branch_id": None, "company_id": company},
        ],
    }


def test_expiry_command_rejects_missing_approved_scopes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EXPIRY_DATABASE_URL", "postgresql://not-used")
    monkeypatch.setenv("WORKLOOP_EXPIRY_PROCESSING_ENABLED", "true")
    monkeypatch.setenv("WORKLOOP_EXPIRY_SCOPES_JSON", "[]")
    monkeypatch.setattr("sys.argv", ["expiry_command"])

    with pytest.raises(SystemExit, match="1"):
        expiry_command.main()

    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == '{"error":"expiry_processing_failed"}\n'
