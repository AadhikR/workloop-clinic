import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [str(item.value) for item in enum_type]


class AccountStatus(enum.StrEnum):
    PENDING_IDENTITY = "pending_identity"
    ACTIVE = "active"
    DISABLED = "disabled"


class AppRole(enum.StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    employees: Mapped[list["Employee"]] = relationship(back_populates="company")
    user_profiles: Mapped[list["UserProfile"]] = relationship(back_populates="company")


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("id", "company_id", name="uq_employees_id_company_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )

    company: Mapped[Company] = relationship(back_populates="employees")
    user_profiles: Mapped[list["UserProfile"]] = relationship(back_populates="employee")


class AppUser(Base):
    __tablename__ = "app_users"
    __table_args__ = (UniqueConstraint("identity_issuer", "identity_subject"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_issuer: Mapped[str] = mapped_column(Text(), nullable=False)
    identity_subject: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status", values_callable=enum_values),
        nullable=False,
        server_default=text("'pending_identity'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    user_profile: Mapped["UserProfile | None"] = relationship(back_populates="app_user")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_id", "company_id"],
            ["employees.id", "employees.company_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(role = 'admin' AND employee_id IS NULL) OR "
            "(role IN ('manager', 'employee') AND employee_id IS NOT NULL)",
            name="role_employee_link",
        ),
    )

    app_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    role: Mapped[AppRole] = mapped_column(
        Enum(AppRole, name="app_role", values_callable=enum_values),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    app_user: Mapped[AppUser] = relationship(back_populates="user_profile")
    company: Mapped[Company] = relationship(back_populates="user_profiles")
    employee: Mapped[Employee | None] = relationship(back_populates="user_profiles")
