import hashlib
import uuid
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from typing import cast

import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.storage.base import StorageError, StorageNotFoundError, StoredObject, StoredObjectMetadata
from app.storage.proof import PROOF_CONTENT, PROOF_CONTENT_TYPE, PROOF_SHA256
from app.storage.spaces import S3Client, SpacesObjectStorage
from tests.test_http_boundary import make_settings


class MemoryObjectStorage:
    def __init__(self, *, fail: bool = False) -> None:
        self.objects: dict[str, StoredObject] = {}
        self.fail = fail
        self.closed = False

    async def put_object(self, *, key: str, body: bytes, content_type: str, sha256: str) -> None:
        if self.fail:
            raise StorageError
        self.objects[key] = StoredObject(
            body=body,
            metadata=StoredObjectMetadata(
                size_bytes=len(body), content_type=content_type, sha256=sha256
            ),
        )

    async def get_object(self, *, key: str) -> StoredObject:
        if self.fail:
            raise StorageError
        try:
            return self.objects[key]
        except KeyError:
            raise StorageNotFoundError from None

    async def head_object(self, *, key: str) -> StoredObjectMetadata:
        return (await self.get_object(key=key)).metadata

    async def delete_object(self, *, key: str) -> None:
        if self.fail:
            raise StorageError
        self.objects.pop(key, None)

    async def close(self) -> None:
        self.closed = True


def active_principal() -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=AppRole.EMPLOYEE,
        company_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
    )


@asynccontextmanager
async def client_for(
    storage: MemoryObjectStorage,
) -> AsyncGenerator[tuple[AsyncClient, FastAPI, AuthorizationPrincipal]]:
    from app.main import create_app

    application = create_app(settings=make_settings(), object_storage=storage)
    principal = active_principal()

    async def claims() -> AccessTokenClaims:
        return AccessTokenClaims(
            issuer="https://seed.workloop.test",
            subject="synthetic-subject",
            audience=("workloop-api",),
            expires_at=1,
            issued_at=1,
            not_before=None,
        )

    async def resolved_principal() -> AuthorizationPrincipal:
        return principal

    application.dependency_overrides[require_access_token] = claims
    application.dependency_overrides[require_authorization_principal] = resolved_principal
    async with (
        application.router.lifespan_context(application),
        AsyncClient(
            transport=ASGITransport(app=application, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client,
    ):
        yield client, application, principal


@pytest.mark.asyncio
async def test_storage_proof_create_read_and_delete_is_identity_bound() -> None:
    storage = MemoryObjectStorage()
    async with client_for(storage) as (client, _application, principal):
        created = await client.post("/api/v1/architecture-proof/storage")
        verified = await client.get("/api/v1/architecture-proof/storage")
        removed = await client.delete("/api/v1/architecture-proof/storage")

    expected_owner = hashlib.sha256(str(principal.app_user_id).encode("ascii")).hexdigest()
    expected = {
        "data": {
            "status": "persisted",
            "sizeBytes": len(PROOF_CONTENT),
            "sha256": PROOF_SHA256,
        }
    }
    assert created.status_code == 201
    assert created.json() == expected
    assert verified.status_code == 200
    assert verified.json() == expected
    assert removed.status_code == 204
    assert removed.content == b""
    assert storage.objects == {}
    assert storage.closed is True
    assert expected_owner not in created.text


@pytest.mark.asyncio
async def test_storage_proof_fails_closed_without_provider_details() -> None:
    storage = MemoryObjectStorage(fail=True)
    async with client_for(storage) as (client, _application, _principal):
        response = await client.post("/api/v1/architecture-proof/storage")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "storage" not in response.text.lower()


@pytest.mark.asyncio
async def test_missing_storage_proof_uses_resource_not_found_contract() -> None:
    storage = MemoryObjectStorage()
    async with client_for(storage) as (client, _application, _principal):
        response = await client.get("/api/v1/architecture-proof/storage")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


class FakeBody:
    def __init__(self, value: bytes) -> None:
        self.value = value
        self.closed = False

    def read(self, amt: int | None = None) -> bytes:
        return self.value if amt is None else self.value[:amt]

    def close(self) -> None:
        self.closed = True


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str, str]] = {}
        self.closed = False

    def put_object(self, **kwargs: object) -> Mapping[str, object]:
        key = cast(str, kwargs["Key"])
        metadata = cast(dict[str, str], kwargs["Metadata"])
        self.objects[key] = (
            cast(bytes, kwargs["Body"]),
            cast(str, kwargs["ContentType"]),
            metadata["sha256"],
        )
        return {}

    def get_object(self, **kwargs: object) -> Mapping[str, object]:
        key = cast(str, kwargs["Key"])
        try:
            body, content_type, sha256 = self.objects[key]
        except KeyError:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "missing"}}, "GetObject"
            ) from None
        return {
            "Body": FakeBody(body),
            "ContentLength": len(body),
            "ContentType": content_type,
            "Metadata": {"sha256": sha256},
        }

    def head_object(self, **kwargs: object) -> Mapping[str, object]:
        response = dict(self.get_object(**kwargs))
        response.pop("Body")
        return response

    def delete_object(self, **kwargs: object) -> Mapping[str, object]:
        self.objects.pop(cast(str, kwargs["Key"]), None)
        return {}

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_spaces_adapter_uses_private_bucket_contract() -> None:
    client = FakeS3Client()
    storage = SpacesObjectStorage(
        endpoint_url="https://fra1.digitaloceanspaces.com",
        region="fra1",
        bucket="workloop-phase-6g-example",
        access_key="not-used",
        secret_key="not-used",
        client=cast(S3Client, client),
    )

    with pytest.raises(StorageNotFoundError):
        await storage.head_object(key="phase-6g/proof.txt")
    await storage.put_object(
        key="phase-6g/proof.txt",
        body=PROOF_CONTENT,
        content_type=PROOF_CONTENT_TYPE,
        sha256=PROOF_SHA256,
    )
    stored = await storage.get_object(key="phase-6g/proof.txt")
    await storage.delete_object(key="phase-6g/proof.txt")
    await storage.close()

    assert stored.body == PROOF_CONTENT
    assert stored.metadata.sha256 == PROOF_SHA256
    assert client.objects == {}
    assert client.closed is True
