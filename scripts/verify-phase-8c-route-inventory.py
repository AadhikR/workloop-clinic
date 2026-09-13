#!/usr/bin/env python3
"""Verify the exact Phase 8C route inventory without importing the application."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "backend/app/leave_balance_api.py"

EXPECTED_ROUTES = {
    ("get", "/balances/self", "get_employee_leave_balances"),
    ("get", "/requests/calendar/self", "get_employee_leave_request_calendar"),
    ("get", "/balances/branch", "get_admin_leave_balances"),
    ("get", "/requests/calendar/branch", "get_admin_leave_request_calendar"),
    ("get", "/balances/approver", "get_approver_leave_balances"),
    ("post", "/balances/initialize", "initialize_leave_balances"),
    ("post", "/balances/recalculate", "recalculate_leave_balances"),
}


def fail(message: str) -> None:
    raise SystemExit(f"Phase 8C route inventory check failed: {message}")


def route_inventory(tree: ast.Module) -> set[tuple[str, str, str]]:
    routes: set[tuple[str, str, str]] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in {"get", "post"}
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and isinstance(decorator.args[0].value, str)
            ):
                continue
            operation = next(
                (
                    keyword.value.value
                    for keyword in decorator.keywords
                    if keyword.arg == "operation_id"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ),
                None,
            )
            if operation is None:
                fail(f"{node.name} has no literal operation_id")
            routes.add((decorator.func.attr, decorator.args[0].value, operation))
    return routes


def main() -> None:
    if not API.is_file():
        fail("backend/app/leave_balance_api.py is missing")
    tree = ast.parse(API.read_text(encoding="utf-8"))
    actual = route_inventory(tree)
    if actual != EXPECTED_ROUTES:
        missing = sorted(EXPECTED_ROUTES - actual)
        unexpected = sorted(actual - EXPECTED_ROUTES)
        fail(f"route mismatch; missing={missing}; unexpected={unexpected}")
    print("Phase 8C route inventory passed")


if __name__ == "__main__":
    main()
