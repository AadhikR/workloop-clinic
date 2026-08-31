import json
import logging
from typing import cast

from app.core.logging import JsonFormatter


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
