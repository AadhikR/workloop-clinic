from app.core.config import Settings
from app.storage.base import ObjectStorage
from app.storage.spaces import DisabledObjectStorage, SpacesObjectStorage


def create_object_storage(settings: Settings) -> ObjectStorage:
    if settings.storage_backend == "disabled":
        return DisabledObjectStorage()
    assert settings.spaces_endpoint_url is not None
    assert settings.spaces_region is not None
    assert settings.spaces_bucket is not None
    assert settings.spaces_access_key is not None
    assert settings.spaces_secret_key is not None
    return SpacesObjectStorage(
        endpoint_url=str(settings.spaces_endpoint_url).rstrip("/"),
        region=settings.spaces_region,
        bucket=settings.spaces_bucket,
        access_key=settings.spaces_access_key.get_secret_value(),
        secret_key=settings.spaces_secret_key.get_secret_value(),
    )
