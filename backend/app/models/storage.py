import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StorageOperation(Base):
    __tablename__ = "storage_operations"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_by_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("operation IN ('upload','delete')", name="operation"),
        CheckConstraint(
            "status IN ('pending','claimed','succeeded','failed','reconciled')", name="status"
        ),
        CheckConstraint("attempt_count BETWEEN 0 AND 8", name="attempt_count"),
        CheckConstraint("entity_type ~ '^[a-z][a-z0-9_]{0,63}$'", name="entity_type"),
        CheckConstraint(
            "octet_length(object_key) BETWEEN 1 AND 1024 "
            "AND object_key !~ '[[:cntrl:]\\\\]' AND left(object_key,1)<>'/' "
            "AND object_key NOT LIKE '%//%' AND ('/'||object_key||'/') NOT LIKE '%/./%' "
            "AND ('/'||object_key||'/') NOT LIKE '%/../%'",
            name="object_key",
        ),
        CheckConstraint(
            "(status='pending' AND attempt_count=0 AND last_error_code='' "
            "AND next_attempt_at IS NULL AND claimed_at IS NULL "
            "AND lease_expires_at IS NULL AND completed_at IS NULL) OR "
            "(status='claimed' AND attempt_count BETWEEN 1 AND 8 AND claimed_at IS NOT NULL "
            "AND lease_expires_at=claimed_at+interval '15 minutes' AND next_attempt_at IS NULL "
            "AND completed_at IS NULL AND last_error_code='') OR "
            "(status='failed' AND attempt_count BETWEEN 1 AND 8 AND completed_at IS NULL "
            "AND claimed_at IS NULL AND lease_expires_at IS NULL AND last_error_code<>' ' "
            "AND last_error_code<>'' AND ((attempt_count<8 AND next_attempt_at IS NOT NULL) "
            "OR (attempt_count=8 AND next_attempt_at IS NULL))) OR "
            "(status IN ('succeeded','reconciled') AND attempt_count BETWEEN 1 AND 8 "
            "AND completed_at IS NOT NULL AND claimed_at IS NULL AND lease_expires_at IS NULL "
            "AND next_attempt_at IS NULL AND last_error_code='')",
            name="lifecycle",
        ),
        CheckConstraint(
            "last_error_code='' OR last_error_code ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="last_error_code",
        ),
        CheckConstraint(
            "updated_at>=created_at AND (next_attempt_at IS NULL OR next_attempt_at>=created_at) "
            "AND (claimed_at IS NULL OR claimed_at>=created_at) "
            "AND (lease_expires_at IS NULL OR lease_expires_at>=created_at) "
            "AND (completed_at IS NULL OR completed_at>=created_at)",
            name="timestamps",
        ),
        Index(
            "ix_storage_operations_claim",
            "status",
            "next_attempt_at",
            "lease_expires_at",
            "created_at",
            "id",
        ),
        Index(
            "ix_storage_operations_purge",
            "completed_at",
            "id",
            postgresql_where=text("status IN ('succeeded','reconciled')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(Text(), nullable=False)
    object_key: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    last_error_code: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )
