from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema


class ContractExpectedSnapshot(StrictRequestSchema):
    employee_updated_at: datetime
    current_contract_type: Literal["Limited", "Unlimited"]
    current_contract_end_date: date | None
    latest_contract_event_id: uuid.UUID | None


class ContractCommandRequest(StrictRequestSchema):
    contract_type: Literal["Limited", "Unlimited"]
    start_date: date | None = None
    end_date: date | None = None
    notes: str = Field(default="", max_length=1000)
    expected: ContractExpectedSnapshot

    @field_validator("notes", mode="before")
    @classmethod
    def trim_notes(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def valid_dates(self) -> ContractCommandRequest:
        if self.contract_type == "Limited":
            if self.start_date is None or self.end_date is None or self.end_date < self.start_date:
                raise ValueError("limited contracts require ordered start and end dates")
        elif self.end_date is not None:
            raise ValueError("unlimited contracts require a null end date")
        return self


class ContractNotRenewedRequest(StrictRequestSchema):
    notes: str = Field(default="", max_length=1000)
    expected: ContractExpectedSnapshot

    @field_validator("notes", mode="before")
    @classmethod
    def trim_notes(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class EmployeeContractResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    contract_type: Literal["Limited", "Unlimited"]
    start_date: date | None
    end_date: date | None
    action: Literal["new", "renewed", "converted", "not_renewed"]
    notes: str
    actor_name: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
