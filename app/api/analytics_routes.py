from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user_id
from app.db.base import get_db
from app.services.analytics_service import compute_analytics


router = APIRouter()


@router.get("/analytics")
async def get_analytics_route(
    db: AsyncSession = Depends(get_db),
    current_user_id: uuid.UUID = Depends(get_current_user_id),
):
    # Run the existing synchronous analytics service through
    # SQLAlchemy's async session bridge.
    data = await db.run_sync(
        lambda sync_db: compute_analytics(
            sync_db,
            current_user_id,
        )
    )

    return {
        "data": data,
        "computed_at": datetime.now(timezone.utc),
    }