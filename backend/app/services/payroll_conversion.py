from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.schemas.payroll import MONEY

MAX_MONEY = Decimal("9999999999.99")


@dataclass(frozen=True)
class LegacyPayrollConversion:
    entry: dict[str, object]
    evidence: tuple[dict[str, str], ...]


def _legacy_money(value: object) -> str:
    if not isinstance(value, str) or MONEY.fullmatch(value) is None:
        raise ValueError("legacy money must use fixed two-decimal notation")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("legacy money is invalid") from None
    if amount > MAX_MONEY:
        raise ValueError("legacy money is outside the accepted range")
    return value


def convert_legacy_payroll_entry(entry: Mapping[str, object]) -> LegacyPayrollConversion:
    """Convert the approved legacy payroll alias without granting it API authority."""
    has_legacy = "duCost" in entry
    has_canonical = "leaveDeduction" in entry
    if has_legacy and has_canonical:
        raise ValueError("legacy and canonical leave deduction fields conflict")

    converted = dict(entry)
    if not has_legacy:
        return LegacyPayrollConversion(entry=converted, evidence=())

    amount = _legacy_money(converted.pop("duCost"))
    converted["leaveDeduction"] = amount
    evidence = (
        {
            "legacySourceField": "duCost",
            "targetField": "leaveDeduction",
            "value": amount,
        },
    )
    return LegacyPayrollConversion(entry=converted, evidence=evidence)
