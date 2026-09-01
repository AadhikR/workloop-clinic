import asyncio
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeGuard, cast

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from jwt.algorithms import RSAAlgorithm

_ALGORITHM = "RS256"
_MAX_JWKS_BYTES = 64 * 1024
_MAX_JWKS_KEYS = 32
_PRIVATE_JWK_MEMBERS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth"})


class AccessTokenError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    issuer: str
    subject: str
    audience: tuple[str, ...]
    expires_at: int
    issued_at: int
    not_before: int | None


class AccessTokenVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        http_client: httpx.AsyncClient,
        total_timeout_seconds: float,
        cache_ttl_seconds: float,
        refresh_cooldown_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks_url = jwks_url
        self._http_client = http_client
        self._total_timeout_seconds = total_timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._refresh_cooldown_seconds = refresh_cooldown_seconds
        self._clock = clock
        self._keys: dict[str, RSAPublicKey] = {}
        self._cache_expires_at = 0.0
        self._last_refresh_attempt_at = float("-inf")
        self._cache_generation = 0
        self._refresh_lock = asyncio.Lock()

    async def verify(self, token: str) -> AccessTokenClaims:
        header = self._read_header(token)
        key_id = header.get("kid")
        if not isinstance(key_id, str) or not key_id or len(key_id) > 256:
            raise AccessTokenError

        keys, generation = await self._get_fresh_keys()
        key = keys.get(key_id)
        if key is None:
            keys = await self._refresh_for_unknown_key(generation)
            key = keys.get(key_id)
        if key is None:
            raise AccessTokenError

        try:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=[_ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": ["iss", "sub", "aud", "exp", "iat", "typ"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except (jwt.InvalidTokenError, TypeError, ValueError) as error:
            raise AccessTokenError from error

        return self._validate_claim_types(payload)

    @staticmethod
    def _read_header(token: str) -> dict[str, Any]:
        if len(token) > 16_384 or token.count(".") != 2:
            raise AccessTokenError
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as error:
            raise AccessTokenError from error
        if header.get("alg") != _ALGORITHM:
            raise AccessTokenError
        if "crit" in header or header.get("b64") is False:
            raise AccessTokenError
        header_type = header.get("typ")
        if header_type is not None and header_type != "JWT":
            raise AccessTokenError
        return header

    async def _get_fresh_keys(self) -> tuple[Mapping[str, RSAPublicKey], int]:
        now = self._clock()
        if self._keys and now < self._cache_expires_at:
            return self._keys, self._cache_generation

        async with self._refresh_lock:
            now = self._clock()
            if self._keys and now < self._cache_expires_at:
                return self._keys, self._cache_generation
            if now - self._last_refresh_attempt_at < self._refresh_cooldown_seconds:
                raise AccessTokenError
            await self._refresh_keys()
            return self._keys, self._cache_generation

    async def _refresh_for_unknown_key(
        self, observed_generation: int
    ) -> Mapping[str, RSAPublicKey]:
        async with self._refresh_lock:
            if self._cache_generation != observed_generation:
                return self._keys
            now = self._clock()
            if now - self._last_refresh_attempt_at < self._refresh_cooldown_seconds:
                return self._keys
            await self._refresh_keys()
            return self._keys

    async def _refresh_keys(self) -> None:
        try:
            async with asyncio.timeout(self._total_timeout_seconds):
                async with self._http_client.stream(
                    "GET", self._jwks_url, headers={"Accept-Encoding": "identity"}
                ) as response:
                    response.raise_for_status()
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise AccessTokenError
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            declared_length = int(content_length)
                        except ValueError as error:
                            raise AccessTokenError from error
                        if declared_length < 0 or declared_length > _MAX_JWKS_BYTES:
                            raise AccessTokenError

                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > _MAX_JWKS_BYTES:
                            raise AccessTokenError
                        body.extend(chunk)
            document = json.loads(body)
            keys = self._parse_jwks(document)
        except (
            TimeoutError,
            httpx.HTTPError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            TypeError,
            ValueError,
        ) as error:
            raise AccessTokenError from error
        finally:
            self._last_refresh_attempt_at = self._clock()

        self._keys = keys
        self._cache_expires_at = self._clock() + self._cache_ttl_seconds
        self._cache_generation += 1

    @staticmethod
    def _parse_jwks(document: Any) -> dict[str, RSAPublicKey]:
        if not isinstance(document, dict):
            raise AccessTokenError
        typed_document = cast(dict[str, object], document)
        raw_keys = typed_document.get("keys")
        if not isinstance(raw_keys, list):
            raise AccessTokenError
        raw_key_values = cast(list[object], raw_keys)
        if not 0 < len(raw_key_values) <= _MAX_JWKS_KEYS:
            raise AccessTokenError

        keys: dict[str, RSAPublicKey] = {}
        for raw_key_value in raw_key_values:
            if not isinstance(raw_key_value, dict):
                raise AccessTokenError
            raw_key = cast(dict[str, object], raw_key_value)
            if (
                raw_key.get("kty") != "RSA"
                or raw_key.get("alg") != _ALGORITHM
                or raw_key.get("use") != "sig"
            ):
                continue
            key_id = raw_key.get("kid")
            if (
                not isinstance(key_id, str)
                or not key_id
                or len(key_id) > 256
                or key_id in keys
                or _PRIVATE_JWK_MEMBERS.intersection(raw_key)
            ):
                raise AccessTokenError
            key_operations = raw_key.get("key_ops")
            if key_operations is not None and (
                not isinstance(key_operations, list) or "verify" not in key_operations
            ):
                raise AccessTokenError
            try:
                public_key = RSAAlgorithm.from_jwk(json.dumps(raw_key))
            except (jwt.PyJWTError, ValueError, TypeError) as error:
                raise AccessTokenError from error
            if not isinstance(public_key, RSAPublicKey):
                raise AccessTokenError
            if public_key.key_size < 2048:
                raise AccessTokenError
            keys[key_id] = public_key
        if not keys:
            raise AccessTokenError
        return keys

    def _validate_claim_types(self, payload: Mapping[str, Any]) -> AccessTokenClaims:
        issuer: object = payload.get("iss")
        subject: object = payload.get("sub")
        expires_at: object = payload.get("exp")
        issued_at: object = payload.get("iat")
        not_before: object = payload.get("nbf")
        token_type: object = payload.get("typ")
        raw_audience: object = payload.get("aud")

        if issuer != self._issuer or not isinstance(issuer, str):
            raise AccessTokenError
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise AccessTokenError
        if not self._is_numeric_date(expires_at) or not self._is_numeric_date(issued_at):
            raise AccessTokenError
        if not_before is not None and not self._is_numeric_date(not_before):
            raise AccessTokenError
        if token_type != "Bearer":
            raise AccessTokenError

        if isinstance(raw_audience, str):
            audience = (raw_audience,)
        elif isinstance(raw_audience, list) and raw_audience:
            audience_values = cast(list[object], raw_audience)
            if not all(isinstance(item, str) and item for item in audience_values):
                raise AccessTokenError
            audience = tuple(cast(list[str], audience_values))
        else:
            raise AccessTokenError
        if self._audience not in audience:
            raise AccessTokenError

        return AccessTokenClaims(
            issuer=issuer,
            subject=subject,
            audience=audience,
            expires_at=expires_at,
            issued_at=issued_at,
            not_before=not_before,
        )

    @staticmethod
    def _is_numeric_date(value: object) -> TypeGuard[int]:
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
