from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class StorageError(Exception):
    pass


class StorageNotFoundError(StorageError):
    pass


class StorageIntegrityError(StorageError):
    pass


class StorageConflictError(StorageError):
    pass


@dataclass(frozen=True, slots=True)
class StoredObjectMetadata:
    size_bytes: int
    content_type: str
    sha256: str


@dataclass(frozen=True, slots=True)
class StoredObject:
    body: bytes
    metadata: StoredObjectMetadata


@dataclass(frozen=True, slots=True)
class SignedDownload:
    url: str
    expires_at: datetime


class ObjectStorage(Protocol):
    async def put_object(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
        sha256: str,
        if_absent: bool = True,
    ) -> None: ...

    async def get_object(self, *, key: str) -> StoredObject: ...

    async def head_object(self, *, key: str) -> StoredObjectMetadata: ...

    async def delete_object(self, *, key: str) -> None: ...

    async def create_download_url(
        self,
        *,
        key: str,
        expires_in_seconds: int,
        download_name: str,
        content_type: str,
    ) -> SignedDownload: ...

    async def close(self) -> None: ...
