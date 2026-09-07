import uuid
from typing import Literal

from pydantic import ConfigDict

from app.http.schemas import ApiSchema
from app.models.identity import AppRole


class PublicStatusResponse(ApiSchema):
    model_config = ConfigDict(strict=True)

    status: Literal["ok"]


class CurrentAccountResponse(ApiSchema):
    model_config = ConfigDict(strict=True)

    app_user_id: uuid.UUID
    role: AppRole
    company_id: uuid.UUID
    employee_id: uuid.UUID | None
    branch_id: uuid.UUID | None
