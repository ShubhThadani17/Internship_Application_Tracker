from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.db.base import get_db
from app.core.dependencies import get_current_user_id
from app.db.models import AnalyticsSnapshot

router = APIRouter()


@router.get("/analytics")
async def get_analytics_route(
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    result = await db.execute(select(AnalyticsSnapshot).where(AnalyticsSnapshot.id == 1))
    snapshot = result.scalar_one_or_none()

    if snapshot is None:
        return {"message": "Analytics not yet computed"}

    return {"data": snapshot.data, "computed_at": snapshot.computed_at}