from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.storage.malware import (
    ScanRecord,
    ScanVerdict,
    SyntheticMalwareScanner,
    scan_allows_download,
)
from app.storage.recovery import (
    RecoveryObject,
    SnapshotError,
    create_encrypted_snapshot,
    restore_encrypted_snapshot,
)
from app.storage.synthetic import SyntheticObjectStorage

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_synthetic_scanner_is_deterministic_and_fails_closed() -> None:
    scanner = SyntheticMalwareScanner(signing_key=b"s" * 32)
    clean_body = b"%PDF-1.7\nsynthetic evidence\n%%EOF\n"
    infected_body = b"%PDF-1.7\nWORKLOOP-SYNTHETIC-MALWARE\n%%EOF\n"

    clean = await scanner.scan_object(
        body=clean_body,
        size_bytes=len(clean_body),
        sha256=hashlib.sha256(clean_body).hexdigest(),
        content_type="application/pdf",
        definition="synthetic-v1",
        scanned_at=NOW,
    )
    repeated = await scanner.scan_object(
        body=clean_body,
        size_bytes=len(clean_body),
        sha256=hashlib.sha256(clean_body).hexdigest(),
        content_type="application/pdf",
        definition="synthetic-v1",
        scanned_at=NOW,
    )
    infected = await scanner.scan_object(
        body=infected_body,
        size_bytes=len(infected_body),
        sha256=hashlib.sha256(infected_body).hexdigest(),
        content_type="application/pdf",
        definition="synthetic-v1",
        scanned_at=NOW,
    )

    assert clean.verdict is ScanVerdict.CLEAN
    assert clean.result_signature == repeated.result_signature
    assert infected.verdict is ScanVerdict.INFECTED
    assert infected.result_signature != clean.result_signature

    record = ScanRecord(
        status="clean",
        object_key="leave-attachments/v1/scope/item",
        size_bytes=len(clean_body),
        content_type="application/pdf",
        sha256=hashlib.sha256(clean_body).hexdigest(),
        scanner_definition="synthetic-v1",
        scanned_at=NOW,
        valid_until=NOW + timedelta(days=30),
    )
    assert scan_allows_download(
        record,
        object_key=record.object_key,
        size_bytes=record.size_bytes,
        content_type=record.content_type,
        sha256=record.sha256,
        scanner_definition="synthetic-v1",
        now=NOW + timedelta(days=29),
    )
    assert not scan_allows_download(
        record,
        object_key=record.object_key,
        size_bytes=record.size_bytes,
        content_type=record.content_type,
        sha256=record.sha256,
        scanner_definition="synthetic-v1",
        now=NOW + timedelta(days=30),
    )


@pytest.mark.asyncio
async def test_encrypted_snapshot_restores_exact_objects_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    source = SyntheticObjectStorage(
        root=tmp_path / "source",
        signing_key=b"1" * 32,
        base_url="http://127.0.0.1:28000",
    )
    target = SyntheticObjectStorage(
        root=tmp_path / "target",
        signing_key=b"2" * 32,
        base_url="http://127.0.0.1:28001",
    )
    bodies = {
        "leave-attachments/v1/scope/one": b"%PDF-1.7\none\n%%EOF\n",
        "expense-receipts/v1/scope/two": (
            b"\x89PNG\r\n\x1a\nsynthetic\x00\x00\x00\x00IEND\xaeB`\x82"
        ),
    }
    objects: list[RecoveryObject] = []
    for index, (key, body) in enumerate(bodies.items(), start=1):
        content_type = "application/pdf" if key.startswith("leave") else "image/png"
        digest = hashlib.sha256(body).hexdigest()
        await source.put_object(
            key=key,
            body=body,
            content_type=content_type,
            sha256=digest,
        )
        objects.append(
            RecoveryObject(
                entity_type="leave_attachment" if index == 1 else "expense_receipt",
                entity_id=f"00000000-0000-4000-8000-{index:012d}",
                object_key=key,
                content_type=content_type,
                size_bytes=len(body),
                sha256=digest,
            )
        )

    snapshot = await create_encrypted_snapshot(
        source,
        objects=objects,
        scan_rows=[{"id": "scan-1", "status": "clean"}],
        operation_rows=[{"id": "operation-1", "status": "succeeded"}],
        encryption_key=b"k" * 32,
        key_id="11b00001",
        created_at=NOW,
    )
    assert bodies[objects[0].object_key] not in snapshot.payload
    assert objects[0].object_key.encode() not in snapshot.payload

    restored = await restore_encrypted_snapshot(
        target,
        payload=snapshot.payload,
        encryption_keys={"11b00001": b"k" * 32},
    )
    assert restored.object_count == 2
    assert restored.manifest_digest == snapshot.manifest_digest
    for item in objects:
        stored = await target.get_object(key=item.object_key)
        assert stored.body == bodies[item.object_key]
        assert stored.metadata.sha256 == item.sha256

    tampered = bytearray(snapshot.payload)
    tampered[-1] ^= 1
    with pytest.raises(SnapshotError):
        await restore_encrypted_snapshot(
            SyntheticObjectStorage(
                root=tmp_path / "tampered",
                signing_key=b"3" * 32,
                base_url="http://127.0.0.1:28002",
            ),
            payload=bytes(tampered),
            encryption_keys={"11b00001": b"k" * 32},
        )
