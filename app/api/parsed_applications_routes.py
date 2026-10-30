from fastapi import APIRouter, Depends,HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.base import get_db
from app.core.dependencies import get_current_user_id
from app.domain.fsm import InvalidTransitionError
from app.services.gemini_service import (
    extract_email_details,
    GeminiServiceError,
)
from app.domain.status_resolver import resolve_status
from app.repositories.application_repository import (
    get_application_by_company_and_role,
    get_application,update_application_status,
    create_application_at_status
)
from app.schemas.parsed_application import ConfirmParsedApplicationRequest, ParsedEmailRequest, ParsedApplicationSuggestion
from app.schemas.application import ApplicationResponse
from app.domain.normalization import (
    normalize_company_name,
    normalize_role_title,
)

router = APIRouter()


@router.post(
    "/parse-email",
    response_model=ParsedApplicationSuggestion,
)
async def parse_email_route(
    payload: ParsedEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    # Call Gemini asynchronously and handle provider errors.
    try:
        extracted = await extract_email_details(payload.raw_text)
    except GeminiServiceError as exc:
        raise HTTPException(
            status_code=exc.http_status_code,
            detail=exc.public_detail,
        ) from exc

    company_name = extracted.get("company_name")
    role_title = extracted.get("role_title")

    if company_name:
        company_name = normalize_company_name(company_name)

    if role_title:
        role_title = normalize_role_title(role_title)

    existing_application = None

    if company_name and role_title:
        existing_application = await get_application_by_company_and_role(
            db=db,
            user_id=current_user_id,
            company_name=company_name,
            role_title=role_title,
        )

    current_status = (
        existing_application.current_status
        if existing_application
        else None
    )

    resolved_status = resolve_status(
        extracted.get("stage"),
        current_status,
    )

    suggestion = ParsedApplicationSuggestion(
        application_id=(
            existing_application.id
            if existing_application
            else None
        ),
        company_name=company_name,
        role_title=role_title,
        suggested_status=resolved_status,
        deadline=extracted.get("deadline"),
        is_new_application=existing_application is None,
    )

    return suggestion


@router.post(
    "/confirm-parsed-application",
    response_model=ApplicationResponse,
)
async def confirm_parsed_application_route(
    payload: ConfirmParsedApplicationRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    # Case 1: Updating an existing application.
    if payload.application_id is not None:
        application = await get_application(
            db=db,
            application_id=payload.application_id,
        )

        if application is None or application.user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found",
            )

        try:
            updated = await update_application_status(
                db=db,
                application=application,
                target_status=payload.suggested_status,
                deadline=payload.deadline,
            )

        except InvalidTransitionError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot transition from {e.current.value} "
                    f"to {e.target.value}"
                ),
            ) from e

        return updated

    # Case 2: Creating a new application.
    # First, check whether the same company + role already exists.
    existing_application = await get_application_by_company_and_role(
        db=db,
        user_id=current_user_id,
        company_name=payload.company_name,
        role_title=payload.role_title,
    )

    if existing_application is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An application for this company and role already exists. "
                "Parse the email again to update the existing application."
            ),
        )

    # Create the new application.
    created = await create_application_at_status(
        db=db,
        user_id=current_user_id,
        company_name=payload.company_name,
        role_title=payload.role_title,
        starting_status=payload.suggested_status,
        deadline=payload.deadline,
    )

    return created