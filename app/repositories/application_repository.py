from datetime import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, StatusHistory
from app.domain.fsm import transition
from app.domain.status import ApplicationStatus


async def create_application(db: AsyncSession,user_id: uuid.UUID,company_name: str,role_title: str,) -> Application:
    application = Application(user_id=user_id,company_name=company_name,role_title=role_title,current_status=ApplicationStatus.APPLIED,)
    db.add(application)
    await db.flush()
    initial_history = StatusHistory(application_id=application.id,from_status=None,to_status=ApplicationStatus.APPLIED,)
    db.add(initial_history)
    await db.commit()
    await db.refresh(application)
    return application


async def get_application(db: AsyncSession, application_id: uuid.UUID) -> Application | None:
    result = await db.execute(select(Application).where(Application.id == application_id))
    return result.scalar_one_or_none()

TERMINAL_STATUSES = {
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
    ApplicationStatus.GHOSTED,
}

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
        application.deadline = None
    elif deadline is not None:
        application.deadline = deadline
        application.deadline_notified = False

    history_entry = StatusHistory(
        application_id=application.id,
        from_status=current_status,
        to_status=new_status,
    )
    db.add(history_entry)
    await db.commit()
    await db.refresh(application)
    return application


async def list_applications_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Application]:
    result = await db.execute(select(Application).where(Application.user_id == user_id))
    return list(result.scalars().all())


async def update_application_fields(
    db: AsyncSession,
    application: Application,
    company_name: str | None = None,
    role_title: str | None = None,
    deadline: datetime | None = None,
) -> Application:
    if company_name is not None:
        application.company_name = company_name

    if role_title is not None:
        application.role_title = role_title

    if deadline is not None:
        application.deadline = deadline
        application.deadline_notified = False

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
    application = Application(
        user_id=user_id,
        company_name=company_name,
        role_title=role_title,
        current_status=starting_status,
        deadline=deadline,
    )
    db.add(application)
    await db.flush()

    history_entry = StatusHistory(
        application_id=application.id,
        from_status=None,
        to_status=starting_status,
    )
    db.add(history_entry)

    await db.commit()
    await db.refresh(application)
    return application