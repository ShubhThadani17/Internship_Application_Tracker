import uuid

from sqlalchemy import select
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


async def update_application_status(db: AsyncSession,application: Application,target_status: ApplicationStatus,) -> Application:
    current_status = application.current_status
    new_status = transition(current_status, target_status)
    application.current_status = new_status
    history_entry = StatusHistory(application_id=application.id,from_status=current_status,to_status=new_status,)
    db.add(history_entry)
    await db.commit()
    await db.refresh(application)
    return application