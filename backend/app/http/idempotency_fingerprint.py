from __future__ import annotations

import hashlib
import json
import unicodedata
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Final, cast

FINGERPRINT_VERSION: Final = "wlp-idem-fp-v1"


class _Absent:
    pass


ABSENT: Final = _Absent()


def _typed(value: object) -> list[object]:
    if isinstance(value, _Absent):
        return ["absent"]
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["boolean", value]
    if isinstance(value, int):
        return ["integer", str(value)]
    if isinstance(value, Enum):
        return ["string", unicodedata.normalize("NFC", str(value.value))]
    if isinstance(value, (uuid.UUID, date, datetime, Decimal)):
        return ["string", unicodedata.normalize("NFC", str(value))]
    if isinstance(value, str):
        return ["string", unicodedata.normalize("NFC", value)]
    if isinstance(value, (list, tuple)):
        items = cast(list[object] | tuple[object, ...], value)
        return ["array", [_typed(item) for item in items]]
    if isinstance(value, dict):
        raw_mapping = cast(dict[object, object], value)
        if not all(isinstance(raw_name, str) for raw_name in raw_mapping):
            raise TypeError("fingerprint object keys must be strings")
        mapping = cast(dict[str, object], raw_mapping)
        pairs: list[list[object]] = []
        for raw_name in sorted(mapping):
            name = unicodedata.normalize("NFC", raw_name)
            pairs.append([name, _typed(mapping[raw_name])])
        return ["object", pairs]
    raise TypeError("unsupported fingerprint value")


def request_fingerprint(
    *,
    operation_id: str,
    method: str,
    route_parameters: dict[str, object],
    effective_query_parameters: dict[str, object],
    body: dict[str, object],
) -> str:
    root: dict[str, object] = {
        "body": body,
        "effectiveQueryParameters": effective_query_parameters,
        "fingerprintVersion": FINGERPRINT_VERSION,
        "method": method,
        "operationId": operation_id,
        "routeParameters": route_parameters,
    }
    typed = _typed(root)
    canonical = json.dumps(
        typed,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
