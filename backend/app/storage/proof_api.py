import logging
from typing import Literal

from fastapi import Request, Response, status
from pydantic import ConfigDict

from app.auth.dependencies import AuthenticatedReadPrincipal, AuthenticatedWritePrincipal
from app.http.errors import api_error
from app.http.schemas import ApiSchema, DataResponse
from app.sample_api import NoAccountQueryInput
from app.storage.base import StorageError, StorageNotFoundError
from app.storage.proof import StorageProofService

logger = logging.getLogger(__name__)


class StorageProofResponse(ApiSchema):
    model_config = ConfigDict(strict=True)

    status: Literal["persisted"]
    size_bytes: int
    sha256: str


def _service(request: Request) -> StorageProofService:
    return StorageProofService(request.app.state.object_storage)


def _response(size_bytes: int, sha256: str) -> DataResponse[StorageProofResponse]:
    return DataResponse(
        data=StorageProofResponse(status="persisted", size_bytes=size_bytes, sha256=sha256)
    )


async def create_storage_proof(
    request: Request,
    principal: AuthenticatedWritePrincipal,
    _query_input: NoAccountQueryInput,
) -> DataResponse[StorageProofResponse]:
    try:
        proof = await _service(request).create(str(principal.app_user_id))
    except StorageError:
        logger.warning("storage_proof_create_failed")
        raise api_error("service_unavailable") from None
    return _response(proof.size_bytes, proof.sha256)


async def read_storage_proof(
    request: Request,
    principal: AuthenticatedReadPrincipal,
    _query_input: NoAccountQueryInput,
) -> DataResponse[StorageProofResponse]:
    try:
        proof = await _service(request).read(str(principal.app_user_id))
    except StorageNotFoundError:
        raise api_error("resource_not_found") from None
    except StorageError:
        logger.warning("storage_proof_read_failed")
        raise api_error("service_unavailable") from None
    return _response(proof.size_bytes, proof.sha256)


async def delete_storage_proof(
    request: Request,
    principal: AuthenticatedWritePrincipal,
    _query_input: NoAccountQueryInput,
) -> Response:
    try:
        await _service(request).delete(str(principal.app_user_id))
    except StorageError:
        logger.warning("storage_proof_delete_failed")
        raise api_error("service_unavailable") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
