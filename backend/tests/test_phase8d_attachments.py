from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.execution import ServiceExecutionError
from app.services.leave_attachment import parse_upload
from app.storage.base import StorageConflictError, StorageNotFoundError
from app.storage.synthetic import SyntheticObjectStorage


def multipart(parts: list[tuple[str, str | None, str | None, bytes]]) -> tuple[str, bytes]:
    boundary = "workloop-phase8d-boundary"
    body = bytearray()
    for name, filename, content_type, value in parts:
        body.extend(f"--{boundary}\r\n".encode())
        disposition = f'Content-Disposition: form-data; name="{name}"'
        if filename is not None:
            disposition += f'; filename="{filename}"'
        body.extend(f"{disposition}\r\n".encode())
        if content_type is not None:
            body.extend(f"Content-Type: {content_type}\r\n".encode())
        body.extend(b"\r\n" + value + b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", bytes(body)


def test_parses_exact_pdf_upload_and_normalizes_filename() -> None:
    file_body = b"%PDF-1.7\nsynthetic\n%%EOF\n"
    digest = hashlib.sha256(file_body).hexdigest()
    token = "wlat1.8d000000-0000-4000-8000-000000000001." + "A" * 43
    content_type, body = multipart(
        [
            ("file", "  proof   FILE.PDF  ", "application/pdf", file_body),
            ("submissionToken", None, None, token.encode()),
            ("sha256", None, None, digest.encode()),
        ]
    )

    upload = parse_upload(content_type, body)

    assert upload.file_name == "proof FILE.pdf"
    assert upload.sha256 == digest
    assert upload.content_type == "application/pdf"


def test_rejects_duplicate_and_mismatched_upload_parts() -> None:
    file_body = b"%PDF-1.7\n%%EOF"
    digest = hashlib.sha256(file_body).hexdigest().encode()
    content_type, body = multipart(
        [
            ("file", "proof.pdf", "application/pdf", file_body),
            ("submissionToken", None, None, b"bad"),
            ("sha256", None, None, digest),
            ("sha256", None, None, digest),
        ]
    )

    with pytest.raises(ServiceExecutionError, match="invalid_request"):
        parse_upload(content_type, body)


@pytest.mark.asyncio
async def test_synthetic_storage_is_conditional_persistent_and_signed(tmp_path: Path) -> None:
    root = tmp_path / "objects"
    key = "leave-attachments/v1/scope/8d000000000040008000000000000001"
    body = b"%PDF-1.7\n%%EOF"
    digest = hashlib.sha256(body).hexdigest()
    storage = SyntheticObjectStorage(
        root=root,
        signing_key=b"1" * 32,
        base_url="http://127.0.0.1:28000",
    )
    await storage.put_object(key=key, body=body, content_type="application/pdf", sha256=digest)
    with pytest.raises(StorageConflictError):
        await storage.put_object(key=key, body=body, content_type="application/pdf", sha256=digest)

    reopened = SyntheticObjectStorage(
        root=root,
        signing_key=b"1" * 32,
        base_url="http://127.0.0.1:28000",
    )
    signed = await reopened.create_download_url(
        key=key,
        expires_in_seconds=300,
        download_name="proof.pdf",
        content_type="application/pdf",
    )
    token = signed.url.rsplit("/", 1)[1]
    stored, name = await reopened.resolve_download(token)
    assert stored.body == body
    assert name == "proof.pdf"

    with pytest.raises(StorageNotFoundError):
        await reopened.resolve_download(token[:-1] + ("A" if token[-1] != "A" else "B"))
