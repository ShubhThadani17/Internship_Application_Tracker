import uuid

from pydantic import BaseModel, Field

from app.domain.status import ApplicationStatus
from datetime import datetime


class ParsedEmailRequest(BaseModel):
    raw_text: str = Field(
        min_length=1,
        max_length=20000,
    )


class ParsedApplicationSuggestion(BaseModel):
    application_id: uuid.UUID | None
    company_name: str | None
    role_title: str | None
    suggested_status: ApplicationStatus | None
    deadline: str | None
    is_new_application: bool


class ConfirmParsedApplicationRequest(BaseModel):
    application_id: uuid.UUID | None
    company_name: str
    role_title: str
    suggested_status: ApplicationStatus
    deadline: datetime | None
    is_new_application: bool