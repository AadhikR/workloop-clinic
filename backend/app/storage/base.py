from dataclasses import dataclass
from typing import Protocol


class StorageError(Exception):
    pass


class StorageNotFoundError(StorageError):
    pass


class StorageIntegrityError(StorageError):
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


class ObjectStorage(Protocol):
    async def put_object(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> None: ...

    async def get_object(self, *, key: str) -> StoredObject: ...

    async def head_object(self, *, key: str) -> StoredObjectMetadata: ...

    async def delete_object(self, *, key: str) -> None: ...

    async def close(self) -> None: ...
