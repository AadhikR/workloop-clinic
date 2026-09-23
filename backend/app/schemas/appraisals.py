from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

AppraisalCycleStatus = Literal["draft", "active", "closed"]
AppraisalStatus = Literal["pending", "reviewed", "calibrated"]


class AppraisalCycleCreateRequest(StrictRequestSchema):
    name: str = Field(min_length=1, max_length=180)
    review_from: date
    review_to: date

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_dates(self) -> AppraisalCycleCreateRequest:
        if self.review_to < self.review_from:
            raise ValueError("reviewTo must be on or after reviewFrom")
        return self


class AppraisalCycleUpdateRequest(AppraisalCycleCreateRequest):
    expected_updated_at: datetime


class AppraisalVersionRequest(StrictRequestSchema):
    expected_updated_at: datetime


class AppraisalSectionRatingRequest(AppraisalVersionRequest):
    rating: Decimal = Field(ge=Decimal("1.0"), le=Decimal("5.0"), multiple_of=0.1)
    comments: str = Field(default="", max_length=10000)

    @field_validator("comments", mode="before")
    @classmethod
    def trim_comments(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AppraisalReviewRequest(AppraisalVersionRequest):
    reviewer_comments: str = Field(default="", max_length=10000)
    development_plan: str = Field(default="", max_length=10000)

    @field_validator("reviewer_comments", "development_plan", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AppraisalCalibrationRequest(AppraisalVersionRequest):
    final_rating: Decimal = Field(ge=Decimal("1.0"), le=Decimal("5.0"), multiple_of=0.1)


class AppraisalSectionResponse(ApiSchema):
    id: uuid.UUID
    section_name: str
    weight: Decimal
    rating: Decimal | None
    comments: str
    sort_order: int
    updated_at: datetime

    @field_serializer("weight")
    def serialize_weight(self, value: Decimal) -> str:
        return f"{value:.2f}"

    @field_serializer("rating")
    def serialize_rating(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.1f}"

    @field_serializer("updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AppraisalResponse(ApiSchema):
    id: uuid.UUID
    cycle_id: uuid.UUID
    cycle_name: str
    review_from: date
    review_to: date
    employee_id: uuid.UUID
    employee_name: str
    template_version: str
    overall_rating: Decimal | None
    status: AppraisalStatus
    reviewer_comments: str
    development_plan: str
    reviewed_at: datetime | None
    reviewed_by_app_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    sections: list[AppraisalSectionResponse]

    @field_serializer("overall_rating")
    def serialize_rating(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.1f}"

    @field_serializer("created_at", "updated_at", "reviewed_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        return (
            None
            if value is None
            else value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        )


class AppraisalCycleResponse(ApiSchema):
    id: uuid.UUID
    name: str
    review_from: date
    review_to: date
    status: AppraisalCycleStatus
    closed_by_app_user_id: uuid.UUID | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    appraisals: list[AppraisalResponse]

    @field_serializer("created_at", "updated_at", "closed_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        return (
            None
            if value is None
            else value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        )


class AppraisalGenerationResponse(ApiSchema):
    cycle_id: uuid.UUID
    created_count: int
    appraisal_count: int
    section_count: int


class DeletedAppraisalCycleResponse(ApiSchema):
    id: uuid.UUID
    deleted: bool
