import json
import logging
from typing import cast

import pytest

from app.core.logging import (
    JsonFormatter,
    SafeLogValueError,
    configure_logging,
    correlation_context,
    safe_event,
    validate_safe_log_value,
)


def test_json_formatter_produces_machine_readable_fields() -> None:
    record = logging.LogRecord(
        name="workloop.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="service_ready",
        args=(),
        exc_info=None,
    )

    payload = cast(dict[str, str], json.loads(JsonFormatter().format(record)))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "workloop.test"
    assert payload["message"] == "service_ready"
    assert payload["timestamp"].endswith("+00:00")


def test_json_formatter_binds_server_correlation_and_safe_error_code() -> None:
    record = logging.LogRecord(
        name="workloop.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="request_rejected",
        args=(),
        exc_info=None,
    )
    record.error_code = "invalid_request"

    with correlation_context("00f202d5-2ef0-4d6f-9553-830e5dcfb833"):
        payload = cast(dict[str, str], json.loads(JsonFormatter().format(record)))

    assert payload["correlationId"] == "00f202d5-2ef0-4d6f-9553-830e5dcfb833"
    assert payload["errorCode"] == "invalid_request"


def test_runtime_logging_disables_path_bearing_access_log() -> None:
    configure_logging("INFO")

    assert logging.getLogger("uvicorn.access").disabled is True


def test_safe_event_keeps_only_contract_fields(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        safe_event(
            logging.getLogger("workloop.test"),
            logging.INFO,
            "worker_queue_observed",
            worker="file_scanner",
            condition="queue-age",
            queue_age_seconds=901,
        )

    payload = cast(dict[str, object], json.loads(JsonFormatter().format(caplog.records[-1])))
    assert payload["message"] == "worker_queue_observed"
    assert payload["worker"] == "file_scanner"
    assert payload["condition"] == "queue-age"
    assert payload["queue_age_seconds"] == 901


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("token", "synthetic"),
        ("status", "Bearer abc"),
        ("resource_id", "postgresql://user:password@db/workloop"),
        ("release_id", "https://objects.invalid/file?signature=abc"),
        ("document_content", "synthetic document text"),
    ],
)
def test_safe_log_values_reject_protected_fields(field: str, value: object) -> None:
    with pytest.raises(SafeLogValueError):
        validate_safe_log_value(field, value)


def test_formatter_replaces_an_unsafe_message_without_echoing_it() -> None:
    record = logging.LogRecord(
        name="workloop.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Bearer synthetic-token",
        args=(),
        exc_info=None,
    )

    rendered = JsonFormatter().format(record)

    assert "synthetic-token" not in rendered
    assert json.loads(rendered)["message"] == "unsafe_log_rejected"


def test_formatter_drops_an_unsafe_correlation_value() -> None:
    record = logging.LogRecord(
        name="workloop.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )

    with correlation_context("Bearer synthetic-token"):
        rendered = JsonFormatter().format(record)

    assert "synthetic-token" not in rendered
    assert "correlationId" not in json.loads(rendered)
