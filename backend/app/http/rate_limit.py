from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class RateLimitClass(StrEnum):
    PUBLIC = "public"
    AUTHENTICATION_CHECK = "authentication_check"
    PROTECTED_ATTEMPT = "protected_attempt"
    INVALID_ACCESS_TOKEN = "invalid_access_token"
    AUTHENTICATED_READ = "authenticated_read"
    AUTHENTICATED_WRITE = "authenticated_write"
    FINANCIAL_OR_APPROVAL = "financial_or_approval"


RATE_LIMITS_PER_MINUTE: dict[RateLimitClass, int] = {
    RateLimitClass.PUBLIC: 60,
    RateLimitClass.AUTHENTICATION_CHECK: 30,
    RateLimitClass.PROTECTED_ATTEMPT: 600,
    RateLimitClass.INVALID_ACCESS_TOKEN: 60,
    RateLimitClass.AUTHENTICATED_READ: 300,
    RateLimitClass.AUTHENTICATED_WRITE: 60,
    RateLimitClass.FINANCIAL_OR_APPROVAL: 20,
}


class RateLimiter(Protocol):
    async def check(self, request_class: RateLimitClass, trusted_key: str) -> int | None:
        """Return Retry-After seconds when the request must be rejected."""


class InactiveRateLimiter:
    async def check(self, request_class: RateLimitClass, trusted_key: str) -> None:
        del request_class, trusted_key
        return None
