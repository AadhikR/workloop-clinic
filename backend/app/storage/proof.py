import hashlib
from dataclasses import dataclass

from app.storage.base import ObjectStorage, StorageIntegrityError, StorageNotFoundError

PROOF_CONTENT = b"workloop-phase-6g-storage-proof-v1\n"
PROOF_CONTENT_TYPE = "text/plain"
PROOF_SHA256 = hashlib.sha256(PROOF_CONTENT).hexdigest()


@dataclass(frozen=True, slots=True)
class StorageProof:
    size_bytes: int
    sha256: str


class StorageProofService:
    def __init__(self, storage: ObjectStorage) -> None:
        self._storage = storage

    async def create(self, app_user_id: str) -> StorageProof:
        key = self._key(app_user_id)
        try:
            await self._storage.head_object(key=key)
        except StorageNotFoundError:
            await self._storage.put_object(
                key=key,
                body=PROOF_CONTENT,
                content_type=PROOF_CONTENT_TYPE,
                sha256=PROOF_SHA256,
            )
        return await self.read(app_user_id)

    async def read(self, app_user_id: str) -> StorageProof:
        stored = await self._storage.get_object(key=self._key(app_user_id))
        metadata = stored.metadata
        if (
            stored.body != PROOF_CONTENT
            or metadata.size_bytes != len(PROOF_CONTENT)
            or metadata.content_type != PROOF_CONTENT_TYPE
            or metadata.sha256 != PROOF_SHA256
        ):
            raise StorageIntegrityError
        return StorageProof(size_bytes=metadata.size_bytes, sha256=metadata.sha256)

    async def delete(self, app_user_id: str) -> None:
        await self._storage.delete_object(key=self._key(app_user_id))

    @staticmethod
    def _key(app_user_id: str) -> str:
        owner = hashlib.sha256(app_user_id.encode("ascii")).hexdigest()
        return f"phase-6g/{owner}/proof-v1.txt"
