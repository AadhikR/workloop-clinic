from fastapi import HTTPException, Request, Response, status

from app.storage.base import StorageNotFoundError
from app.storage.synthetic import SyntheticObjectStorage


async def download_synthetic_object(token: str, request: Request) -> Response:
    storage = request.app.state.object_storage
    if not isinstance(storage, SyntheticObjectStorage):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        stored, download_name = await storage.resolve_download(token)
    except StorageNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from None
    safe_name = download_name.replace('"', "").replace("\r", "").replace("\n", "")
    return Response(
        content=stored.body,
        media_type=stored.metadata.content_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
