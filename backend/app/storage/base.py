import hashlib
import re
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


MAX_PRIVATE_OBJECT_BYTES = 10_485_760
PRIVATE_CONTENT_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})


def validate_object_write(*, body: bytes, content_type: str, sha256: str) -> None:
    if (
        not 1 <= len(body) <= MAX_PRIVATE_OBJECT_BYTES
        or content_type not in PRIVATE_CONTENT_TYPES
        or re.fullmatch(r"[0-9a-f]{64}", sha256) is None
        or hashlib.sha256(body).hexdigest() != sha256
    ):
        raise StorageIntegrityError


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
