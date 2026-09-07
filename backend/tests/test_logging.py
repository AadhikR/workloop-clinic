import json
import logging
from typing import cast

from app.core.logging import JsonFormatter, configure_logging, correlation_context


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
