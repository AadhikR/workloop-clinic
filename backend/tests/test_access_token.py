import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import fields
from typing import Any
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jwt.algorithms import RSAAlgorithm

from app.auth.access_token import AccessTokenError, AccessTokenVerifier
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.auth.dependencies import VerifiedAccessToken
from app.models.identity import AccountStatus, AppRole

ISSUER = "http://127.0.0.1:8080/realms/workloop-dev"
AUDIENCE = "workloop-api"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"


class MutableClock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class JwksEndpoint:
    def __init__(self, document: Mapping[str, Any]) -> None:
        self.document = document
        self.failure: Exception | None = None
        self.request_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.request_count += 1
        if self.failure is not None:
            raise self.failure
        return httpx.Response(200, json=self.document, request=request)


class OversizedStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b"{" + (b" " * (64 * 1024))
        yield b"}"


class SlowStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        while True:
            await asyncio.sleep(0.01)
            yield b" "


@pytest.fixture(scope="module")
def signing_keys() -> Iterator[tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey]]:
    yield tuple(rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(3))  # type: ignore[misc]


def make_jwk(private_key: rsa.RSAPrivateKey, key_id: str) -> dict[str, Any]:
    jwk: dict[str, Any] = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": key_id, "alg": "RS256", "use": "sig", "key_ops": ["verify"]})
    return jwk


def make_claims(**overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "sub": "synthetic-subject",
        "aud": AUDIENCE,
        "exp": now + 300,
        "iat": now,
        "typ": "Bearer",
    }
    claims.update(overrides)
    return claims


def make_token(
    private_key: rsa.RSAPrivateKey | str,
    key_id: str,
    *,
    claims: Mapping[str, Any] | None = None,
    algorithm: str = "RS256",
    header_type: str = "JWT",
) -> str:
    return jwt.encode(
        dict(claims or make_claims()),
        private_key,
        algorithm=algorithm,
        headers={"kid": key_id, "typ": header_type},
    )


def make_verifier(
    endpoint: JwksEndpoint,
    clock: MutableClock,
    *,
    cache_ttl_seconds: float = 10,
    refresh_cooldown_seconds: float = 1,
) -> tuple[AccessTokenVerifier, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(endpoint))
    return (
        AccessTokenVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            jwks_url=JWKS_URL,
            http_client=client,
            total_timeout_seconds=1,
            cache_ttl_seconds=cache_ttl_seconds,
            refresh_cooldown_seconds=refresh_cooldown_seconds,
            clock=clock,
        ),
        client,
    )


@pytest.mark.asyncio
async def test_valid_token_uses_cold_then_warm_cache(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, client = make_verifier(endpoint, MutableClock())
    token = make_token(key, "current-key")

    try:
        first = await verifier.verify(token)
        second = await verifier.verify(token)
    finally:
        await client.aclose()

    assert first.subject == second.subject == "synthetic-subject"
    assert endpoint.request_count == 1


@pytest.mark.parametrize(
    ("claim_changes", "removed_claim"),
    [
        ({"exp": int(time.time()) - 1}, None),
        ({"nbf": int(time.time()) + 300}, None),
        ({"iss": "http://127.0.0.1:8080/realms/other"}, None),
        ({"aud": "other-api"}, None),
        ({"sub": ""}, None),
        ({"sub": 123}, None),
        ({"exp": "9999999999"}, None),
        ({"iat": True}, None),
        ({"aud": [AUDIENCE, 123]}, None),
        ({"typ": "ID"}, None),
        ({}, "sub"),
        ({}, "iss"),
        ({}, "aud"),
        ({}, "exp"),
        ({}, "iat"),
        ({}, "typ"),
    ],
    ids=[
        "expired",
        "not-yet-valid",
        "wrong-issuer",
        "wrong-audience",
        "empty-subject",
        "non-string-subject",
        "string-expiry",
        "boolean-issued-at",
        "malformed-audience",
        "id-token",
        "missing-subject",
        "missing-issuer",
        "missing-audience",
        "missing-expiry",
        "missing-issued-at",
        "missing-token-type",
    ],
)
@pytest.mark.asyncio
async def test_invalid_access_token_claims_are_rejected(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
    claim_changes: dict[str, Any],
    removed_claim: str | None,
) -> None:
    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, client = make_verifier(endpoint, MutableClock())
    claims = make_claims(**claim_changes)
    if removed_claim is not None:
        claims.pop(removed_claim)

    try:
        with pytest.raises(AccessTokenError):
            await verifier.verify(make_token(key, "current-key", claims=claims))
    finally:
        await client.aclose()


@pytest.mark.parametrize("algorithm", ["RS384", "HS256"])
@pytest.mark.asyncio
async def test_token_selected_algorithm_is_rejected_before_jwks_request(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
    algorithm: str,
) -> None:
    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, client = make_verifier(endpoint, MutableClock())
    signing_key: rsa.RSAPrivateKey | str = (
        key if algorithm.startswith("RS") else "symmetric-key-with-at-least-32-bytes"
    )

    try:
        with pytest.raises(AccessTokenError):
            await verifier.verify(make_token(signing_key, "current-key", algorithm=algorithm))
    finally:
        await client.aclose()

    assert endpoint.request_count == 0


@pytest.mark.asyncio
async def test_none_algorithm_and_malformed_jwt_are_rejected_without_jwks_request() -> None:
    endpoint = JwksEndpoint({"keys": []})
    verifier, client = make_verifier(endpoint, MutableClock())
    unsigned = jwt.encode(
        make_claims(), key="", algorithm="none", headers={"kid": "none-key", "typ": "JWT"}
    )

    try:
        for token in (unsigned, "not-a-jwt", "a.b.c.d", "a..c"):
            with pytest.raises(AccessTokenError):
                await verifier.verify(token)
    finally:
        await client.aclose()

    assert endpoint.request_count == 0


@pytest.mark.asyncio
async def test_invalid_signature_and_header_metadata_are_rejected(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    trusted_key, attacker_key, _ = signing_keys
    endpoint = JwksEndpoint({"keys": [make_jwk(trusted_key, "current-key")]})
    verifier, client = make_verifier(endpoint, MutableClock())
    missing_key_id = jwt.encode(
        make_claims(), trusted_key, algorithm="RS256", headers={"typ": "JWT"}
    )
    invalid_tokens = [
        make_token(attacker_key, "current-key"),
        missing_key_id,
        make_token(trusted_key, "current-key", header_type="JWE"),
        make_token(
            trusted_key,
            "current-key",
            claims=make_claims(padding="x" * 17_000),
        ),
        jwt.encode(
            make_claims(),
            trusted_key,
            algorithm="RS256",
            headers={"kid": "current-key", "typ": "JWT", "crit": ["unsupported"]},
        ),
    ]

    try:
        for token in invalid_tokens:
            with pytest.raises(AccessTokenError):
                await verifier.verify(token)
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore:The RSA key is 1024 bits.*")
async def test_weak_rsa_signing_key_is_rejected() -> None:
    weak_key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    endpoint = JwksEndpoint({"keys": [make_jwk(weak_key, "weak-key")]})
    verifier, client = make_verifier(endpoint, MutableClock())

    try:
        with pytest.raises(AccessTokenError):
            await verifier.verify(make_token(weak_key, "weak-key"))
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_future_issued_at_is_rejected(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, client = make_verifier(endpoint, MutableClock())

    try:
        with pytest.raises(AccessTokenError):
            await verifier.verify(
                make_token(key, "current-key", claims=make_claims(iat=int(time.time()) + 300))
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_unknown_key_refreshes_once_then_fails_closed(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    current_key, unknown_key, _ = signing_keys
    clock = MutableClock()
    endpoint = JwksEndpoint({"keys": [make_jwk(current_key, "current-key")]})
    verifier, client = make_verifier(endpoint, clock)

    try:
        await verifier.verify(make_token(current_key, "current-key"))
        clock.advance(2)
        with pytest.raises(AccessTokenError):
            await verifier.verify(make_token(unknown_key, "unknown-key"))
    finally:
        await client.aclose()

    assert endpoint.request_count == 2


@pytest.mark.asyncio
async def test_unknown_key_refresh_accepts_signing_key_rotation(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    old_key, new_key, _ = signing_keys
    clock = MutableClock()
    endpoint = JwksEndpoint({"keys": [make_jwk(old_key, "old-key")]})
    verifier, client = make_verifier(endpoint, clock)

    try:
        await verifier.verify(make_token(old_key, "old-key"))
        clock.advance(2)
        endpoint.document = {"keys": [make_jwk(old_key, "old-key"), make_jwk(new_key, "new-key")]}
        claims = await verifier.verify(make_token(new_key, "new-key"))
    finally:
        await client.aclose()

    assert claims.subject == "synthetic-subject"
    assert endpoint.request_count == 2


@pytest.mark.asyncio
async def test_temporary_outage_uses_only_unexpired_cached_keys_and_recovers(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]
    clock = MutableClock()
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, client = make_verifier(endpoint, clock, cache_ttl_seconds=5)
    token = make_token(key, "current-key")

    try:
        await verifier.verify(token)
        endpoint.failure = httpx.ConnectError("synthetic outage")
        await verifier.verify(token)
        clock.advance(6)
        with pytest.raises(AccessTokenError):
            await verifier.verify(token)
        assert endpoint.request_count == 2

        endpoint.failure = None
        clock.advance(2)
        await verifier.verify(token)
    finally:
        await client.aclose()

    assert endpoint.request_count == 3


@pytest.mark.asyncio
async def test_cold_start_outage_is_throttled_then_recovers(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]
    clock = MutableClock()
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    endpoint.failure = httpx.ReadTimeout("synthetic timeout")
    verifier, client = make_verifier(endpoint, clock)
    token = make_token(key, "current-key")

    try:
        with pytest.raises(AccessTokenError):
            await verifier.verify(token)
        with pytest.raises(AccessTokenError):
            await verifier.verify(token)
        assert endpoint.request_count == 1

        endpoint.failure = None
        clock.advance(2)
        await verifier.verify(token)
    finally:
        await client.aclose()

    assert endpoint.request_count == 2


@pytest.mark.asyncio
async def test_malformed_and_unsafe_jwks_fail_closed(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]
    base_jwk = make_jwk(key, "current-key")
    invalid_documents: list[Mapping[str, Any]] = [
        {"keys": []},
        {"keys": [base_jwk, base_jwk]},
        {"keys": [{**base_jwk, "alg": "RS384"}]},
        {"keys": [{**base_jwk, "use": "enc"}]},
        {"keys": [{**base_jwk, "d": "private-material"}]},
    ]

    for document in invalid_documents:
        endpoint = JwksEndpoint(document)
        verifier, client = make_verifier(endpoint, MutableClock())
        try:
            with pytest.raises(AccessTokenError):
                await verifier.verify(make_token(key, "current-key"))
        finally:
            await client.aclose()


@pytest.mark.asyncio
async def test_jwks_ignores_unrelated_keys_and_uses_rs256_signing_key(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    signing_key, encryption_key, _ = signing_keys
    encryption_jwk = make_jwk(encryption_key, "encryption-key")
    encryption_jwk.update({"alg": "RSA-OAEP", "use": "enc", "key_ops": ["encrypt"]})
    endpoint = JwksEndpoint(
        {
            "keys": [
                encryption_jwk,
                {"kid": "unrelated-key", "kty": "EC", "alg": "ES256", "use": "sig"},
                make_jwk(signing_key, "signing-key"),
            ]
        }
    )
    verifier, client = make_verifier(endpoint, MutableClock())

    try:
        claims = await verifier.verify(make_token(signing_key, "signing-key"))
    finally:
        await client.aclose()

    assert claims.subject == "synthetic-subject"


@pytest.mark.asyncio
async def test_oversized_chunked_jwks_stops_at_limit(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]

    def oversized_endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=OversizedStream(), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(oversized_endpoint))
    verifier = AccessTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        http_client=client,
        total_timeout_seconds=1,
        cache_ttl_seconds=10,
        refresh_cooldown_seconds=1,
    )
    try:
        with pytest.raises(AccessTokenError):
            await verifier.verify(make_token(key, "current-key"))
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_jwks_fetch_has_total_deadline(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]

    def slow_endpoint(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=SlowStream(), request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(slow_endpoint))
    verifier = AccessTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        http_client=client,
        total_timeout_seconds=0.03,
        cache_ttl_seconds=10,
        refresh_cooldown_seconds=1,
    )
    try:
        with pytest.raises(AccessTokenError):
            await verifier.verify(make_token(key, "current-key"))
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_concurrent_outage_requests_share_completion_based_cooldown(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]
    clock = MutableClock()
    request_count = 0

    async def slow_outage(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        await asyncio.sleep(0.01)
        clock.advance(2)
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(slow_outage))
    verifier = AccessTokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        jwks_url=JWKS_URL,
        http_client=client,
        total_timeout_seconds=1,
        cache_ttl_seconds=10,
        refresh_cooldown_seconds=1,
        clock=clock,
    )
    token = make_token(key, "current-key")

    try:
        results = await asyncio.gather(
            *(verifier.verify(token) for _ in range(5)), return_exceptions=True
        )
    finally:
        await client.aclose()

    assert all(isinstance(result, AccessTokenError) for result in results)
    assert request_count == 1


def protected_test_app(verifier: AccessTokenVerifier) -> FastAPI:
    application = FastAPI()
    application.state.access_token_verifier = verifier

    async def protected(_claims: VerifiedAccessToken) -> dict[str, bool]:
        return {"authenticated": True}

    application.add_api_route("/protected", protected, methods=["GET"])

    return application


@pytest.mark.asyncio
async def test_token_check_accepts_valid_token_without_returning_claims(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    from app.main import create_app

    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, jwks_client = make_verifier(endpoint, MutableClock())
    application = create_app()
    application.state.access_token_verifier = verifier
    application_user_resolver = AsyncMock(spec=ApplicationUserResolver)
    application_user_resolver.resolve.return_value = AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=AppRole.ADMIN,
        company_id=uuid.uuid4(),
        employee_id=None,
        branch_id=None,
    )
    application.state.application_user_resolver = application_user_resolver

    try:
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/api/v1/auth/token-check",
                headers={"Authorization": f"Bearer {make_token(key, 'current-key')}"},
            )
    finally:
        await jwks_client.aclose()

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    application_user_resolver.resolve.assert_awaited_once_with(
        issuer=ISSUER,
        subject="synthetic-subject",
    )


@pytest.mark.asyncio
async def test_email_and_untrusted_authorization_claims_are_not_returned_by_verifier(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, client = make_verifier(endpoint, MutableClock())

    try:
        first = await verifier.verify(
            make_token(
                key,
                "current-key",
                claims=make_claims(
                    email="first@example.test",
                    realm_access={"roles": ["admin"]},
                    resource_access={"workloop-api": {"roles": ["admin"]}},
                    company_id="browser-company",
                    employee_id="browser-employee",
                ),
            )
        )
        second = await verifier.verify(
            make_token(
                key,
                "current-key",
                claims=make_claims(
                    email="changed@example.test",
                    realm_access={"roles": ["employee"]},
                    company_id="other-browser-company",
                ),
            )
        )
    finally:
        await client.aclose()

    assert first == second
    assert tuple(field.name for field in fields(first)) == (
        "issuer",
        "subject",
        "audience",
        "expires_at",
        "issued_at",
        "not_before",
    )


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Basic abc",
        "Bearer",
        "Bearer ",
        "Bearer  abc",
        "Bearer abc def",
        "NotBearer abc",
    ],
)
@pytest.mark.asyncio
async def test_missing_and_malformed_authorization_headers_return_consistent_401(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
    authorization: str | None,
) -> None:
    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, jwks_client = make_verifier(endpoint, MutableClock())
    headers = {} if authorization is None else {"Authorization": authorization}

    try:
        async with AsyncClient(
            transport=ASGITransport(app=protected_test_app(verifier)),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/protected", headers=headers)
    finally:
        await jwks_client.aclose()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "detail": {
            "code": "invalid_access_token",
            "message": "Authentication required",
        }
    }
    assert endpoint.request_count == 0


@pytest.mark.asyncio
async def test_duplicate_authorization_headers_are_rejected(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
) -> None:
    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    verifier, jwks_client = make_verifier(endpoint, MutableClock())

    try:
        async with AsyncClient(
            transport=ASGITransport(app=protected_test_app(verifier)),
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                "/protected",
                headers=[("Authorization", "Bearer first"), ("Authorization", "Bearer second")],
            )
    finally:
        await jwks_client.aclose()

    assert response.status_code == 401
    assert endpoint.request_count == 0


@pytest.mark.asyncio
async def test_errors_and_logs_do_not_expose_token_claims_or_internal_failures(
    signing_keys: tuple[rsa.RSAPrivateKey, rsa.RSAPrivateKey, rsa.RSAPrivateKey],
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = signing_keys[0]
    endpoint = JwksEndpoint({"keys": [make_jwk(key, "current-key")]})
    endpoint.failure = httpx.ConnectError("raw-provider-error")
    verifier, jwks_client = make_verifier(endpoint, MutableClock())
    token = make_token(key, "current-key", claims=make_claims(private_claim="sensitive-claim"))

    caplog.set_level(logging.DEBUG)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=protected_test_app(verifier)),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    finally:
        await jwks_client.aclose()

    combined_output = response.text + caplog.text
    assert response.status_code == 401
    assert token not in combined_output
    assert "sensitive-claim" not in combined_output
    assert "synthetic-subject" not in combined_output
    assert "raw-provider-error" not in combined_output
