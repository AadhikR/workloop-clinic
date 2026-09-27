import json
import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

SAFE_LOG_FIELDS = frozenset(
    {
        "attempt_count",
        "business_date",
        "component",
        "condition",
        "count",
        "database",
        "duration_ms",
        "error_code",
        "inserted_count",
        "lease_age_seconds",
        "method",
        "outcome",
        "processing_enabled",
        "queue_age_seconds",
        "release_id",
        "scope_count",
        "signal_id",
        "status",
        "status_code",
        "worker",
    }
)
_SAFE_EVENT = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_SAFE_TEXT = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
_SAFE_CORRELATION_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_PROTECTED_VALUE = re.compile(
    r"(?i)(bearer\s|password|secret|token|private[ _-]?key|postgres(?:ql)?://|"
    r"https?://|x-amz-(?:signature|credential)|-----begin|[?&](?:sig|signature)=)"
)


class SafeLogValueError(ValueError):
    pass


def validate_safe_log_value(field: str, value: object) -> object:
    if field not in SAFE_LOG_FIELDS:
        raise SafeLogValueError("log field is not allowed")
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 0:
            raise SafeLogValueError("log integer must be nonnegative")
        return value
    if (
        isinstance(value, str)
        and _SAFE_TEXT.fullmatch(value)
        and not _PROTECTED_VALUE.search(value)
    ):
        return value
    raise SafeLogValueError("log value is not safe")


def safe_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: object,
) -> None:
    if not _SAFE_EVENT.fullmatch(event):
        raise SafeLogValueError("log event is not safe")
    safe_fields = {field: validate_safe_log_value(field, value) for field, value in fields.items()}
    logger.log(level, event, extra=safe_fields)


@contextmanager
def correlation_context(correlation_id: str) -> Generator[None]:
    token = _correlation_id.set(correlation_id)
    try:
        yield
    finally:
        _correlation_id.reset(token)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if not _SAFE_EVENT.fullmatch(message) or _PROTECTED_VALUE.search(message):
            message = "unsafe_log_rejected"
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name if _SAFE_TEXT.fullmatch(record.name) else "workloop.unsafe",
            "message": message,
        }
        correlation_id = _correlation_id.get()
        if correlation_id is not None and _SAFE_CORRELATION_ID.fullmatch(correlation_id):
            payload["correlationId"] = correlation_id
        for field in SAFE_LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                try:
                    payload[field] = validate_safe_log_value(field, value)
                except SafeLogValueError:
                    payload = {
                        "timestamp": payload["timestamp"],
                        "level": "ERROR",
                        "logger": payload["logger"],
                        "message": "unsafe_log_rejected",
                    }
                    break
        if "error_code" in payload:
            payload["errorCode"] = payload.pop("error_code")
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    for logger_name in (None, "uvicorn", "uvicorn.error"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.disabled = True
    access_logger.propagate = False
