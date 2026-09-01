import uuid
from datetime import datetime
        
from pydantic import BaseModel

from app.domain.status import ApplicationStatus


class ApplicationCreate(BaseModel):
    company_name: str
    role_title: str


class ApplicationStatusUpdate(BaseModel):
    target_status: ApplicationStatus
    deadline: datetime | None = None


class ApplicationFieldsUpdate(BaseModel):
    company_name: str | None = None
    role_title: str | None = None
    deadline: datetime | None = None


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    company_name: str
    role_title: str
    current_status: ApplicationStatus
    applied_date: datetime
    deadline: datetime | None
    deadline_notified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StatusHistoryResponse(BaseModel):
    id: uuid.UUID
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    changed_at: datetime

    model_config = {"from_attributes": True}