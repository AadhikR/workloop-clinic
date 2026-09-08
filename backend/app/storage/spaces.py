from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Protocol, cast

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.base import (
    StorageError,
    StorageNotFoundError,
    StoredObject,
    StoredObjectMetadata,
)


class ResponseBody(Protocol):
    def read(self, amt: int | None = None) -> bytes: ...

    def close(self) -> None: ...


class S3Client(Protocol):
    def put_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def get_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def head_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def delete_object(self, **kwargs: object) -> Mapping[str, object]: ...

    def close(self) -> None: ...


class DisabledObjectStorage:
    async def put_object(self, **_kwargs: object) -> None:
        raise StorageError

    async def get_object(self, **_kwargs: object) -> StoredObject:
        raise StorageError

    async def head_object(self, **_kwargs: object) -> StoredObjectMetadata:
        raise StorageError

    async def delete_object(self, **_kwargs: object) -> None:
        raise StorageError

    async def close(self) -> None:
        return None


class SpacesObjectStorage:
    def __init__(
        self,
        *,
        endpoint_url: str,
        region: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        client: S3Client | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or cast(
            S3Client,
            boto3.client(  # pyright: ignore[reportUnknownMemberType]
                "s3",
                endpoint_url=endpoint_url,
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=2,
                    read_timeout=5,
                    retries={"max_attempts": 2, "mode": "standard"},
                    s3={"addressing_style": "virtual"},
                ),
            ),
        )

    async def put_object(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> None:
        await self._call(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            Metadata={"sha256": sha256},
        )

    async def get_object(self, *, key: str) -> StoredObject:
        response = await self._call(self._client.get_object, Bucket=self._bucket, Key=key)
        raw_body = response.get("Body")
        if raw_body is None:
            raise StorageError
        body = cast(ResponseBody, raw_body)
        try:
            content = await asyncio.to_thread(body.read, 1025)
        finally:
            body.close()
        if len(content) > 1024:
            raise StorageError
        return StoredObject(body=content, metadata=self._metadata(response))

    async def head_object(self, *, key: str) -> StoredObjectMetadata:
        response = await self._call(self._client.head_object, Bucket=self._bucket, Key=key)
        return self._metadata(response)

    async def delete_object(self, *, key: str) -> None:
        await self._call(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)

    async def _call(
        self,
        operation: object,
        **kwargs: object,
    ) -> Mapping[str, object]:
        try:
            return await asyncio.to_thread(cast(S3Operation, operation), **kwargs)
        except ClientError as error:
            response = cast(Mapping[str, object], error.response)
            details = cast(Mapping[str, object], response.get("Error", {}))
            if details.get("Code") in {"404", "NoSuchKey", "NotFound"}:
                raise StorageNotFoundError from None
            raise StorageError from None
        except BotoCoreError:
            raise StorageError from None

    @staticmethod
    def _metadata(response: Mapping[str, object]) -> StoredObjectMetadata:
        raw_metadata = cast(Mapping[str, object], response.get("Metadata", {}))
        sha256 = raw_metadata.get("sha256")
        content_type = response.get("ContentType")
        size_bytes = response.get("ContentLength")
        if (
            not isinstance(sha256, str)
            or not isinstance(content_type, str)
            or not isinstance(size_bytes, int)
        ):
            raise StorageError
        return StoredObjectMetadata(
            size_bytes=size_bytes,
            content_type=content_type,
            sha256=sha256,
        )


class S3Operation(Protocol):
    def __call__(self, **kwargs: object) -> Mapping[str, object]: ...
