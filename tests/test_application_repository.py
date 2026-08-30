import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, StatusHistory, User
from app.domain.fsm import InvalidTransitionError
from app.domain.status import ApplicationStatus
from app.repositories.application_repository import (
    create_application,
    get_application,
    update_application_status,
)


@pytest.mark.asyncio
async def test_create_application(db: AsyncSession, test_user: User):
    # Act
    application = await create_application(
        db=db,
        user_id=test_user.id,
        company_name="Google",
        role_title="Software Engineer Intern",
    )

    # Assert - Application
    assert application.id is not None
    assert application.user_id == test_user.id
    assert application.company_name == "Google"
    assert application.role_title == "Software Engineer Intern"
    assert application.current_status == ApplicationStatus.APPLIED
    assert application.deadline is None

    # Assert - Initial StatusHistory
    result = await db.execute(
        select(StatusHistory).where(
            StatusHistory.application_id == application.id
        )
    )

    history = result.scalar_one()

    assert history.application_id == application.id
    assert history.from_status is None
    assert history.to_status == ApplicationStatus.APPLIED


@pytest.mark.asyncio
async def test_get_application(db: AsyncSession, test_user: User):
    # Arrange
    application = await create_application(
        db=db,
        user_id=test_user.id,
        company_name="Microsoft",
        role_title="Backend Intern",
    )

    # Act
    result = await get_application(
        db=db,
        application_id=application.id,
    )

    # Assert
    assert result is not None
    assert result.id == application.id
    assert result.user_id == test_user.id
    assert result.company_name == "Microsoft"
    assert result.role_title == "Backend Intern"


@pytest.mark.asyncio
async def test_get_application_not_found(db: AsyncSession):
    # Arrange
    random_application_id = uuid.uuid4()

    # Act
    result = await get_application(
        db=db,
        application_id=random_application_id,
    )

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_update_application_status(db: AsyncSession, test_user: User):
    # Arrange
    application = await create_application(
        db=db,
        user_id=test_user.id,
        company_name="Amazon",
        role_title="Software Engineer Intern",
    )

    # Act
    updated_application = await update_application_status(
        db=db,
        application=application,
        target_status=ApplicationStatus.OA1,
    )

    # Assert - Application status
    assert updated_application.current_status == ApplicationStatus.OA1

    # Assert - StatusHistory
    result = await db.execute(
        select(StatusHistory)
        .where(StatusHistory.application_id == application.id)
        .order_by(StatusHistory.changed_at)
    )

    history_entries = list(result.scalars().all())

    assert len(history_entries) == 2

    initial_history = history_entries[0]
    status_change = history_entries[1]

    assert initial_history.from_status is None
    assert initial_history.to_status == ApplicationStatus.APPLIED

    assert status_change.from_status == ApplicationStatus.APPLIED
    assert status_change.to_status == ApplicationStatus.OA1


@pytest.mark.asyncio
async def test_invalid_status_transition(db: AsyncSession, test_user: User):
    # Arrange
    application = await create_application(
        db=db,
        user_id=test_user.id,
        company_name="Meta",
        role_title="Backend Intern",
    )

    # Act + Assert
    with pytest.raises(InvalidTransitionError):
        await update_application_status(
            db=db,
            application=application,
            target_status=ApplicationStatus.OFFER,
        )


@pytest.mark.asyncio
async def test_status_transition_with_deadline_persists(
    db: AsyncSession, test_user: User
):
    # Arrange
    application = await create_application(
        db=db,
        user_id=test_user.id,
        company_name="Uber",
        role_title="Backend Intern",
    )
    oa1_deadline = datetime.now(timezone.utc) + timedelta(days=5)

    # Act
    updated_application = await update_application_status(
        db=db,
        application=application,
        target_status=ApplicationStatus.OA1,
        deadline=oa1_deadline,
    )

    # Assert
    assert updated_application.deadline == oa1_deadline


@pytest.mark.asyncio
async def test_status_transition_without_deadline_leaves_existing_unchanged(
    db: AsyncSession, test_user: User
):
    # Arrange
    application = await create_application(
        db=db,
        user_id=test_user.id,
        company_name="Uber",
        role_title="Backend Intern",
    )
    oa1_deadline = datetime.now(timezone.utc) + timedelta(days=5)
    application = await update_application_status(
        db=db,
        application=application,
        target_status=ApplicationStatus.OA1,
        deadline=oa1_deadline,
    )

    # Act - transition again without passing a deadline
    updated_application = await update_application_status(
        db=db,
        application=application,
        target_status=ApplicationStatus.OA2,
    )

    # Assert - previous deadline is untouched
    assert updated_application.deadline == oa1_deadline


@pytest.mark.parametrize(
    "terminal_status",
    [
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.GHOSTED,
    ],
)
@pytest.mark.asyncio
async def test_terminal_status_clears_existing_deadline(
    db: AsyncSession, test_user: User, terminal_status: ApplicationStatus
):
    # Arrange
    application = await create_application(
        db=db,
        user_id=test_user.id,
        company_name="Uber",
        role_title="Backend Intern",
    )
    oa1_deadline = datetime.now(timezone.utc) + timedelta(days=5)
    application = await update_application_status(
        db=db,
        application=application,
        target_status=ApplicationStatus.OA1,
        deadline=oa1_deadline,
    )

    # Act
    updated_application = await update_application_status(
        db=db,
        application=application,
        target_status=terminal_status,
    )

    # Assert
    assert updated_application.deadline is None


@pytest.mark.parametrize(
    "terminal_status",
    [
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.GHOSTED,
    ],
)
@pytest.mark.asyncio
async def test_terminal_status_ignores_passed_deadline(
    db: AsyncSession, test_user: User, terminal_status: ApplicationStatus
):
    # Arrange
    application = await create_application(
        db=db,
        user_id=test_user.id,
        company_name="Uber",
        role_title="Backend Intern",
    )
    new_deadline = datetime.now(timezone.utc) + timedelta(days=3)

    # Act - pass a deadline alongside a terminal transition
    updated_application = await update_application_status(
        db=db,
        application=application,
        target_status=terminal_status,
        deadline=new_deadline,
    )

    # Assert - terminal clear wins regardless of the passed value
    assert updated_application.deadline is None