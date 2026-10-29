from datetime import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, StatusHistory
from app.domain.fsm import transition
from app.domain.status import ApplicationStatus


TERMINAL_STATUSES = {
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.GHOSTED,
}


def _reset_notification(application: Application, status: str) -> None:
    """Reset notification metadata when its current schedule is invalidated."""
    application.deadline_notification_status = status
    application.deadline_notification_queued_at = None
    application.deadline_notified = False


async def create_application(
    db: AsyncSession,
    user_id: uuid.UUID,
    company_name: str,
    role_title: str,
) -> Application:
    application = Application(
        user_id=user_id,
        company_name=company_name,
        role_title=role_title,
        current_status=ApplicationStatus.APPLIED,
    )

    db.add(application)
    await db.flush()

    db.add(
        StatusHistory(
            application_id=application.id,
            from_status=None,
            to_status=ApplicationStatus.APPLIED,
        )
    )

    await db.commit()
    await db.refresh(application)
    return application


async def get_application(
    db: AsyncSession,
    application_id: uuid.UUID,
) -> Application | None:
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    return result.scalar_one_or_none()


async def update_application_status(
    db: AsyncSession,
    application: Application,
    target_status: ApplicationStatus,
    deadline: datetime | None = None,
) -> Application:
    current_status = application.current_status
    new_status = transition(current_status, target_status)

    application.current_status = new_status

    if new_status in TERMINAL_STATUSES:
        # A terminal application must not retain an active deadline.
        application.deadline = None
        _reset_notification(application, "cancelled")

    elif deadline is not None:
        deadline_changed = application.deadline != deadline
        application.deadline = deadline

        if deadline_changed:
            # A new deadline needs a fresh notification.
            _reset_notification(application, "pending")

    db.add(
        StatusHistory(
            application_id=application.id,
            from_status=current_status,
            to_status=new_status,
        )
    )

    await db.commit()
    await db.refresh(application)
    return application


async def list_applications_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[Application]:
    result = await db.execute(
        select(Application).where(Application.user_id == user_id)
    )
    return list(result.scalars().all())


async def update_application_fields(
    db: AsyncSession,
    application: Application,
    updates: dict,
) -> Application:
    if (
        "company_name" in updates
        and updates["company_name"] is not None
    ):
        application.company_name = updates["company_name"]

    if "role_title" in updates and updates["role_title"] is not None:
        application.role_title = updates["role_title"]

    if "deadline" in updates:
        new_deadline = updates["deadline"]
        deadline_changed = application.deadline != new_deadline

        application.deadline = new_deadline

        if new_deadline is None:
            # Clearing a deadline cancels any outstanding reminder.
            _reset_notification(application, "cancelled")

        elif deadline_changed:
            # A changed deadline needs a new reminder.
            _reset_notification(application, "pending")

    await db.commit()
    await db.refresh(application)
    return application


async def get_application_by_company_name(
    db: AsyncSession,
    user_id: uuid.UUID,
    company_name: str,
) -> Application | None:
    result = await db.execute(
        select(Application).where(
            Application.user_id == user_id,
            func.lower(Application.company_name) == company_name.lower(),
        )
    )
    return result.scalar_one_or_none()


async def create_application_at_status(
    db: AsyncSession,
    user_id: uuid.UUID,
    company_name: str,
    role_title: str,
    starting_status: ApplicationStatus,
    deadline: datetime | None = None,
) -> Application:
    terminal = starting_status in TERMINAL_STATUSES

    application = Application(
        user_id=user_id,
        company_name=company_name,
        role_title=role_title,
        current_status=starting_status,
        deadline=None if terminal else deadline,
        deadline_notification_status=(
            "cancelled" if terminal else "pending"
        ),
        deadline_notification_queued_at=None,
        deadline_notified=False,
    )

    db.add(application)
    await db.flush()

    db.add(
        StatusHistory(
            application_id=application.id,
            from_status=None,
            to_status=starting_status,
        )
    )

    await db.commit()
    await db.refresh(application)
    return application