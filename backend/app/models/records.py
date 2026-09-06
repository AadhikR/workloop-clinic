import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"
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
        ForeignKeyConstraint(["reviewed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint("file_size >= 0", name="file_size"),
        CheckConstraint(
            "status IN ('pending_verification', 'verified', 'rejected')", name="status"
        ),
        CheckConstraint("submitted_by IN ('hr', 'employee')", name="submitted_by"),
        CheckConstraint(
            "status = 'pending_verification' OR (reviewed_by_app_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL)",
            name="review_fields",
        ),
        CheckConstraint(
            "status <> 'rejected' OR btrim(rejection_reason) <> ''", name="rejection_fields"
        ),
        Index("ix_employee_documents_employee_id", "employee_id"),
        Index("ix_employee_documents_branch_id_expiry_date", "branch_id", "expiry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    document_type: Mapped[str] = mapped_column(Text(), nullable=False)
    document_number: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    file_name: Mapped[str] = mapped_column(Text(), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    storage_path: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    expiry_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'verified'"))
    rejection_reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    submitted_by: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'hr'"))
    reviewed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_insurance_policies_id_company_id_branch_id"
        ),
        CheckConstraint("annual_premium >= 0", name="annual_premium"),
        Index("ix_insurance_policies_branch_id_renewal_date", "branch_id", "renewal_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    insurer_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    policy_number: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    tier_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    annual_premium: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    renewal_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    broker_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    broker_contact: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class EmployeeInsurance(Base):
    __tablename__ = "employee_insurance"
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
            ["policy_id", "company_id", "branch_id"],
            [
                "insurance_policies.id",
                "insurance_policies.company_id",
                "insurance_policies.branch_id",
            ],
            ondelete="SET NULL (policy_id)",
        ),
        UniqueConstraint("employee_id", name="uq_employee_insurance_employee_id"),
        CheckConstraint(
            "expiry_date IS NULL OR effective_date IS NULL OR expiry_date >= effective_date",
            name="dates",
        ),
        Index("ix_employee_insurance_branch_id_expiry_date", "branch_id", "expiry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    member_id: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    card_number: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    effective_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    tier_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class InsuranceDependant(Base):
    __tablename__ = "insurance_dependants"
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
        Index("ix_insurance_dependants_employee_id", "employee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    relationship: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    date_of_birth: Mapped[date | None] = mapped_column(Date(), nullable=True)
    card_number: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="SET NULL (branch_id)",
        ),
        ForeignKeyConstraint(
            ["recipient_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            name="fk_notifications_recipient_app_user_id_user_profiles",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_by_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            name="fk_notifications_created_by_app_user_id_user_profiles",
            ondelete="SET NULL (created_by_app_user_id)",
        ),
        UniqueConstraint(
            "company_id",
            "recipient_app_user_id",
            "type",
            "related_entity_type",
            "related_entity_id",
            name="uq_notifications_dedup",
        ),
        Index("ix_notifications_recipient_app_user_id", "recipient_app_user_id"),
        Index(
            "ix_notifications_unread",
            "recipient_app_user_id",
            text("created_at DESC"),
            postgresql_where=text("read_at IS NULL"),
        ),
        Index("ix_notifications_company_id_branch_id", "company_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    recipient_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(Text(), nullable=False)
    title: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    body: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    related_entity_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    related_entity_id: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class EmployeeContract(Base):
    __tablename__ = "employee_contracts"
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
        ForeignKeyConstraint(["renewed_by_app_user_id"], ["app_users.id"], ondelete="SET NULL"),
        CheckConstraint("action IN ('new', 'renewed', 'converted', 'not_renewed')", name="action"),
        CheckConstraint("contract_type IN ('Limited', 'Unlimited')", name="contract_type"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="dates"
        ),
        Index("ix_employee_contracts_employee_id", "employee_id"),
        Index("ix_employee_contracts_branch_id_end_date", "branch_id", "end_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    contract_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'Limited'")
    )
    start_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    renewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    renewed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    action: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'new'"))
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class OffboardingChecklist(Base):
    __tablename__ = "offboarding_checklists"
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
        ForeignKeyConstraint(["completed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint("employee_id", name="uq_offboarding_checklists_employee_id"),
        UniqueConstraint(
            "id",
            "company_id",
            "branch_id",
            name="uq_offboarding_checklists_id_company_id_branch_id",
        ),
        CheckConstraint("status IN ('in_progress', 'completed')", name="status"),
        CheckConstraint(
            "visa_cancellation_status IN ('not_started', 'initiated', 'submitted_gdrfa', "
            "'cancelled')",
            name="visa_cancellation_status",
        ),
        CheckConstraint(
            "status <> 'completed' OR (completed_by_app_user_id IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="completed_fields",
        ),
        Index("ix_offboarding_checklists_branch_id_status", "branch_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'in_progress'")
    )
    visa_cancellation_status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'not_started'")
    )
    visa_cancellation_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class OffboardingTask(Base):
    __tablename__ = "offboarding_tasks"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["checklist_id", "company_id", "branch_id"],
            [
                "offboarding_checklists.id",
                "offboarding_checklists.company_id",
                "offboarding_checklists.branch_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["completed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint(
            "NOT completed OR (completed_by_app_user_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="completed_fields",
        ),
        Index("ix_offboarding_tasks_checklist_id_sort_order", "checklist_id", "sort_order"),
        Index("ix_offboarding_tasks_company_id_branch_id", "company_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_name: Mapped[str] = mapped_column(Text(), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("false"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class OffboardingTaskTemplate(Base):
    __tablename__ = "offboarding_task_templates"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "branch_id", "task_name", name="uq_offboarding_task_templates_branch_id_task_name"
        ),
        Index("ix_offboarding_task_templates_branch_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_name: Mapped[str] = mapped_column(Text(), nullable=False)
    default_order: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "company_id", "branch_id", name="uq_assets_id_company_id_branch_id"),
        CheckConstraint(
            "status IN ('available', 'assigned', 'under_repair', 'retired', 'lost')",
            name="status",
        ),
        CheckConstraint("purchase_cost IS NULL OR purchase_cost >= 0", name="purchase_cost"),
        Index("ix_assets_branch_id_status", "branch_id", "status"),
        Index(
            "uq_assets_branch_id_asset_code_nonempty",
            "branch_id",
            "asset_code",
            unique=True,
            postgresql_where=text("btrim(asset_code) <> ''"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    asset_code: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    category: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'other'"))
    brand: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    model: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    serial_number: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    purchase_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'available'"))
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AssetAssignment(Base):
    __tablename__ = "asset_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["asset_id", "company_id", "branch_id"],
            ["assets.id", "assets.company_id", "assets.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["assigned_by_app_user_id"], ["app_users.id"], ondelete="SET NULL"),
        CheckConstraint("return_date IS NULL OR return_date >= assigned_date", name="dates"),
        Index("ix_asset_assignments_asset_id", "asset_id"),
        Index("ix_asset_assignments_employee_id", "employee_id"),
        Index(
            "uq_asset_assignments_open_asset",
            "asset_id",
            unique=True,
            postgresql_where=text("return_date IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assigned_date: Mapped[date] = mapped_column(
        Date(), nullable=False, server_default=text("CURRENT_DATE")
    )
    return_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    condition_at_handover: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'good'")
    )
    condition_at_return: Mapped[str | None] = mapped_column(Text(), nullable=True)
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    assigned_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class TrainingRecord(Base):
    __tablename__ = "training_records"
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
        CheckConstraint("cost >= 0", name="cost"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="dates"
        ),
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'cancelled')", name="status"
        ),
        CheckConstraint("duration_hours IS NULL OR duration_hours >= 0", name="duration_hours"),
        CheckConstraint("status <> 'completed' OR end_date IS NOT NULL", name="completed_fields"),
        Index("ix_training_records_employee_id", "employee_id"),
        Index("ix_training_records_branch_id_status", "branch_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    training_title: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    training_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'external'")
    )
    provider: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    start_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    duration_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'planned'"))
    score: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    passed: Mapped[bool | None] = mapped_column(Boolean(), nullable=True)
    certificate_url: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    storage_path: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    file_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    is_cme: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Certification(Base):
    __tablename__ = "certifications"
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
        ForeignKeyConstraint(["reviewed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint(
            "expiry_date IS NULL OR issued_date IS NULL OR expiry_date >= issued_date",
            name="dates",
        ),
        CheckConstraint("status IN ('pending_review', 'verified', 'rejected')", name="status"),
        CheckConstraint(
            "status = 'pending_review' OR (reviewed_by_app_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL)",
            name="review_fields",
        ),
        CheckConstraint("status <> 'rejected' OR btrim(notes) <> ''", name="rejection_fields"),
        Index("ix_certifications_employee_id", "employee_id"),
        Index("ix_certifications_branch_id_expiry_date", "branch_id", "expiry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    certification_name: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    issuing_body: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    certificate_no: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    issued_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    certificate_url: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    storage_path: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    file_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'verified'"))
    reviewed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AppraisalCycle(Base):
    __tablename__ = "appraisal_cycles"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["closed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_appraisal_cycles_id_company_id_branch_id"
        ),
        UniqueConstraint("branch_id", "name", name="uq_appraisal_cycles_branch_id_name"),
        CheckConstraint("review_to >= review_from", name="dates"),
        CheckConstraint("status IN ('draft', 'active', 'closed')", name="status"),
        CheckConstraint(
            "status <> 'closed' OR (closed_by_app_user_id IS NOT NULL AND closed_at IS NOT NULL)",
            name="closed_fields",
        ),
        Index("ix_appraisal_cycles_branch_id_status", "branch_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    review_from: Mapped[date] = mapped_column(Date(), nullable=False)
    review_to: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'draft'"))
    closed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Appraisal(Base):
    __tablename__ = "appraisals"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["cycle_id", "company_id", "branch_id"],
            [
                "appraisal_cycles.id",
                "appraisal_cycles.company_id",
                "appraisal_cycles.branch_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["reviewed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint("cycle_id", "employee_id", name="uq_appraisals_cycle_id_employee_id"),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_appraisals_id_company_id_branch_id"
        ),
        CheckConstraint(
            "overall_rating IS NULL OR overall_rating BETWEEN 1 AND 5", name="overall_rating"
        ),
        CheckConstraint("self_rating IS NULL OR self_rating BETWEEN 1 AND 5", name="self_rating"),
        CheckConstraint("status IN ('pending', 'reviewed', 'calibrated')", name="status"),
        CheckConstraint(
            "status = 'pending' OR (reviewed_by_app_user_id IS NOT NULL "
            "AND reviewed_at IS NOT NULL)",
            name="review_fields",
        ),
        Index("ix_appraisals_cycle_id", "cycle_id"),
        Index("ix_appraisals_employee_id", "employee_id"),
        Index("ix_appraisals_branch_id_status", "branch_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    overall_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    self_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'pending'"))
    reviewer_comments: Mapped[str | None] = mapped_column(Text(), nullable=True)
    development_plan: Mapped[str | None] = mapped_column(Text(), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AppraisalSection(Base):
    __tablename__ = "appraisal_sections"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["appraisal_id", "company_id", "branch_id"],
            ["appraisals.id", "appraisals.company_id", "appraisals.branch_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "appraisal_id",
            "section_name",
            name="uq_appraisal_sections_appraisal_id_section_name",
        ),
        CheckConstraint("weight > 0", name="weight"),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="rating"),
        CheckConstraint("self_rating IS NULL OR self_rating BETWEEN 1 AND 5", name="self_rating"),
        Index("ix_appraisal_sections_appraisal_id_sort_order", "appraisal_id", "sort_order"),
        Index("ix_appraisal_sections_company_id_branch_id", "company_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    appraisal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    section_name: Mapped[str] = mapped_column(Text(), nullable=False)
    weight: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default=text("1.0")
    )
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    self_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    comments: Mapped[str | None] = mapped_column(Text(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))


class CmeRequirement(Base):
    __tablename__ = "cme_requirements"
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
        UniqueConstraint("employee_id", "year", name="uq_cme_requirements_employee_id_year"),
        CheckConstraint("required_hours >= 0", name="required_hours"),
        Index("ix_cme_requirements_employee_id", "employee_id"),
        Index("ix_cme_requirements_year", "year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    year: Mapped[int] = mapped_column(Integer(), nullable=False)
    required_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 1), nullable=False, server_default=text("25")
    )
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class IncidentReport(Base):
    __tablename__ = "incident_reports"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reported_by_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_incident_reports_reported_by_id_employees",
            ondelete="SET NULL (reported_by_id)",
        ),
        ForeignKeyConstraint(
            ["involved_emp_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_incident_reports_involved_emp_id_employees",
            ondelete="SET NULL (involved_emp_id)",
        ),
        ForeignKeyConstraint(["closed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint(
            "incident_type IN ('patient_safety', 'medication_error', 'injury', 'needlestick', "
            "'infection', 'equipment', 'near_miss', 'workplace', 'other')",
            name="incident_type",
        ),
        CheckConstraint("severity IN ('low', 'moderate', 'high', 'critical')", name="severity"),
        CheckConstraint("status IN ('open', 'investigating', 'closed')", name="status"),
        CheckConstraint(
            "status <> 'closed' OR (closed_by_app_user_id IS NOT NULL AND closed_date IS NOT NULL)",
            name="closed_fields",
        ),
        Index("ix_incident_reports_branch_id_incident_date", "branch_id", "incident_date"),
        Index("ix_incident_reports_status", "status"),
        Index("ix_incident_reports_department", "department"),
        Index("ix_incident_reports_severity", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    incident_date: Mapped[date] = mapped_column(Date(), nullable=False)
    incident_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    location: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    department: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    incident_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'other'")
    )
    severity: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'low'"))
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    reported_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    involved_emp_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    immediate_action: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    root_cause: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    corrective_action: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'open'"))
    closed_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    closed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class LetterRequest(Base):
    __tablename__ = "letter_requests"
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
        ForeignKeyConstraint(["actioned_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint("request_kind IN ('letter', 'custom')", name="request_kind"),
        CheckConstraint("status IN ('pending', 'completed', 'rejected')", name="status"),
        CheckConstraint(
            "status <> 'completed' OR (actioned_by_app_user_id IS NOT NULL "
            "AND actioned_at IS NOT NULL AND completed_at IS NOT NULL)",
            name="completed_fields",
        ),
        CheckConstraint(
            "status <> 'rejected' OR (actioned_by_app_user_id IS NOT NULL "
            "AND actioned_at IS NOT NULL AND btrim(rejection_reason) <> '')",
            name="rejected_fields",
        ),
        CheckConstraint(
            "request_kind <> 'custom' OR (char_length(btrim(letter_type)) BETWEEN 3 AND 120 "
            "AND char_length(btrim(purpose)) BETWEEN 5 AND 2000)",
            name="custom_lengths",
        ),
        Index("ix_letter_requests_employee_id", "employee_id"),
        Index("ix_letter_requests_branch_id_status", "branch_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    request_kind: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'letter'")
    )
    letter_type: Mapped[str] = mapped_column(Text(), nullable=False)
    purpose: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'pending'"))
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    rejection_reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actioned_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["actor_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            name="fk_audit_events_actor_profile",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["initiated_by_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            name="fk_audit_events_initiator_profile",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "actor_kind IN ('human','scheduled_job','migration','seed','system_rule')",
            name="actor_kind",
        ),
        CheckConstraint(
            "(actor_kind = 'human' AND actor_app_user_id IS NOT NULL "
            "AND system_actor_key IS NULL) OR (actor_kind <> 'human' "
            "AND actor_app_user_id IS NULL AND btrim(system_actor_key) <> '')",
            name="primary_actor",
        ),
        CheckConstraint("btrim(action) <> ''", name="action_nonblank"),
        CheckConstraint("btrim(entity_type) <> ''", name="entity_type_nonblank"),
        CheckConstraint("btrim(reason) <> ''", name="reason_nonblank"),
        CheckConstraint("array_position(changed_fields, NULL) IS NULL", name="changed_fields"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_object"),
        Index("ix_audit_events_company_id_occurred_at", "company_id", text("occurred_at DESC")),
        Index(
            "ix_audit_events_company_id_branch_id_occurred_at",
            "company_id",
            "branch_id",
            text("occurred_at DESC"),
        ),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    actor_kind: Mapped[str] = mapped_column(Text(), nullable=False)
    actor_app_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    system_actor_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    initiated_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    action: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text(), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(ARRAY(Text()), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB(), nullable=False, server_default=text("'{}'::jsonb")
    )
