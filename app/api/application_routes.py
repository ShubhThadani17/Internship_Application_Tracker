import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id, get_owned_application
from app.db.base import get_db
from app.db.models import Application
from app.domain.fsm import InvalidTransitionError
from app.repositories.application_repository import (
    create_application,
    list_applications_for_user,
    update_application_fields,
    update_application_status,
)
from app.schemas.application import (
    ApplicationCreate,
    ApplicationFieldsUpdate,
    ApplicationResponse,
    ApplicationStatusUpdate,
)

from app.tasks.analytics_tasks import recompute_analytics

router = APIRouter()


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application_route(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    application = await create_application(
        db=db,
        user_id=user_id,
        company_name=payload.company_name,
        role_title=payload.role_title,
    )
    return application


@router.get("", response_model=list[ApplicationResponse])
async def list_applications_route(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    return await list_applications_for_user(db=db, user_id=user_id)


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application_route(
    application: Application = Depends(get_owned_application),
):
    return application


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application_fields_route(
    payload: ApplicationFieldsUpdate,
    db: AsyncSession = Depends(get_db),
    application: Application = Depends(get_owned_application),
):
    updated = await update_application_fields(
        db=db,
        application=application,
        company_name=payload.company_name,
        role_title=payload.role_title,
    )
    return updated


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def update_status_route(
    payload: ApplicationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    application: Application = Depends(get_owned_application),
):
    try:
        updated = await update_application_status(
            db=db,
            application=application,
            target_status=payload.target_status,
            deadline=payload.deadline,
        )
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from {e.current.value} to {e.target.value}",
        )

    recompute_analytics.delay()

    return updated