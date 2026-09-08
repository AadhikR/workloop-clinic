from __future__ import annotations

import asyncio
from enum import StrEnum
from time import monotonic
from typing import Protocol


class RateLimitClass(StrEnum):
    PUBLIC = "public"
    AUTHENTICATION_CHECK = "authentication_check"
    PROTECTED_ATTEMPT = "protected_attempt"
    INVALID_ACCESS_TOKEN = "invalid_access_token"
    AUTHENTICATED_READ_USER = "authenticated_read_user"
    AUTHENTICATED_READ_COMPANY = "authenticated_read_company"
    AUTHENTICATED_WRITE_USER = "authenticated_write_user"
    AUTHENTICATED_WRITE_COMPANY = "authenticated_write_company"
    FINANCIAL_OR_APPROVAL_USER = "financial_or_approval_user"
    FINANCIAL_OR_APPROVAL_COMPANY = "financial_or_approval_company"


RATE_LIMITS_PER_MINUTE: dict[RateLimitClass, int] = {
    RateLimitClass.PUBLIC: 60,
    RateLimitClass.AUTHENTICATION_CHECK: 30,
    RateLimitClass.PROTECTED_ATTEMPT: 600,
    RateLimitClass.INVALID_ACCESS_TOKEN: 60,
    RateLimitClass.AUTHENTICATED_READ_USER: 300,
    RateLimitClass.AUTHENTICATED_READ_COMPANY: 3_000,
    RateLimitClass.AUTHENTICATED_WRITE_USER: 60,
    RateLimitClass.AUTHENTICATED_WRITE_COMPANY: 600,
    RateLimitClass.FINANCIAL_OR_APPROVAL_USER: 20,
    RateLimitClass.FINANCIAL_OR_APPROVAL_COMPANY: 200,
}


class RateLimiter(Protocol):
    async def check(self, request_class: RateLimitClass, trusted_key: str) -> int | None:
        """Return Retry-After seconds when the request must be rejected."""


class InactiveRateLimiter:
    async def check(self, request_class: RateLimitClass, trusted_key: str) -> None:
        del request_class, trusted_key
        return None


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._window = -1
        self._counts: dict[tuple[RateLimitClass, str], int] = {}
        self._lock = asyncio.Lock()

    async def check(self, request_class: RateLimitClass, trusted_key: str) -> int | None:
        current_time = monotonic()
        window = int(current_time // 60)
        async with self._lock:
            if window != self._window:
                self._window = window
                self._counts.clear()
            key = (request_class, trusted_key)
            count = self._counts.get(key, 0) + 1
            self._counts[key] = count
            if count <= RATE_LIMITS_PER_MINUTE[request_class]:
                return None
        return max(1, int((window + 1) * 60 - current_time))


class ConfigurableRateLimiter:
    def __init__(self, *, deployed: bool = False) -> None:
        self._delegate: RateLimiter = (
            FixedWindowRateLimiter() if deployed else InactiveRateLimiter()
        )

    def configure(self, *, deployed: bool) -> None:
        self._delegate = FixedWindowRateLimiter() if deployed else InactiveRateLimiter()

    async def check(self, request_class: RateLimitClass, trusted_key: str) -> int | None:
        return await self._delegate.check(request_class, trusted_key)
