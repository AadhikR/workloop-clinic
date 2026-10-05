from datetime import UTC, datetime


def same_instant(actual: object, expected: object) -> bool:
    if (
        not isinstance(actual, datetime)
        or not isinstance(expected, datetime)
        or expected.tzinfo is None
        or actual.tzinfo is None
    ):
        return False

    def milliseconds(value: datetime) -> datetime:
        value = value.astimezone(UTC)
        return value.replace(microsecond=value.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)
