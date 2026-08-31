import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.base import get_db
from app.db.models import Application
from app.repositories.application_repository import get_application

bearer_scheme = HTTPBearer()


async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> uuid.UUID:
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid or expired token",)

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Token is not an access token",)

    return uuid.UUID(payload["sub"])


async def get_owned_application(application_id: uuid.UUID,db: AsyncSession = Depends(get_db),user_id: uuid.UUID = Depends(get_current_user_id),) -> Application:
    application = await get_application(db=db, application_id=application_id)

    if application is None or application.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    return application