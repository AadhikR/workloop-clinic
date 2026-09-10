import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            name="fk_idempotency_records_actor_profile",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_idempotency_records_company",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_idempotency_records_branch",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "substring(idempotency_key::text, 15, 1) = '4'",
            name="idempotency_key_uuid4",
        ),
        CheckConstraint(
            "operation_id ~ '^[a-z][a-z0-9_]{0,127}$'",
            name="operation_id",
        ),
        CheckConstraint(
            "http_method IN ('POST','PATCH','PUT','DELETE')",
            name="http_method",
        ),
        CheckConstraint("jsonb_typeof(route_parameters) = 'object'", name="route_parameters"),
        CheckConstraint(
            "fingerprint_version ~ '^wlp-idem-fp-v[1-9][0-9]{0,3}$'",
            name="fingerprint_version",
        ),
        CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="request_fingerprint",
        ),
        CheckConstraint(
            "replay_resource_kind IS NULL OR replay_resource_kind ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="replay_resource_kind",
        ),
        CheckConstraint(
            "(completed_at IS NULL AND replay_resource_kind IS NULL "
            "AND replay_resource_id IS NULL AND response_status IS NULL "
            "AND response_body IS NULL AND response_location IS NULL "
            "AND retain_until IS NULL) OR "
            "(completed_at IS NOT NULL AND replay_resource_kind IS NOT NULL "
            "AND response_status BETWEEN 200 AND 299 AND retain_until IS NOT NULL "
            "AND ((response_status = 204 AND response_body IS NULL) "
            "OR (response_status <> 204 AND jsonb_typeof(response_body) = 'object'))) ",
            name="completion_state",
        ),
        CheckConstraint(
            "response_location IS NULL OR "
            "(response_status IN (201,202) AND octet_length(response_location) <= 2048 "
            "AND response_location LIKE '/%' AND response_location NOT LIKE '//%' "
            "AND position(chr(13) in response_location) = 0 "
            "AND position(chr(10) in response_location) = 0)",
            name="response_location",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="completed_at",
        ),
        CheckConstraint(
            "retain_until IS NULL OR retain_until >= completed_at + interval '7 days'",
            name="retention_floor",
        ),
        CheckConstraint(
            "(replay_resource_kind IN ('branch','employee','department','user_profile') "
            "AND replay_resource_id IS NOT NULL) "
            "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
            "OR replay_resource_kind IS NULL",
            name="replay_resource",
        ),
        Index(
            "ix_idempotency_records_company_retention",
            "company_id",
            "retain_until",
            "created_at",
        ),
    )

    app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    operation_id: Mapped[str] = mapped_column(Text(), nullable=False)
    http_method: Mapped[str] = mapped_column(Text(), nullable=False)
    route_parameters: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False)
    fingerprint_version: Mapped[str] = mapped_column(Text(), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text(), nullable=False)
    replay_resource_kind: Mapped[str | None] = mapped_column(Text(), nullable=True)
    replay_resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    response_status: Mapped[int | None] = mapped_column(SmallInteger(), nullable=True)
    response_body: Mapped[dict[str, object] | None] = mapped_column(JSONB(), nullable=True)
    response_location: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
