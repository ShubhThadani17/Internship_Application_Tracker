import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import redis_client
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.core.config import settings
from app.db.models import User


REFRESH_TOKEN_PREFIX = "refresh_token"


async def issue_tokens(user_id: uuid.UUID) -> tuple[str, str]:
    access_token = create_access_token(user_id)
    refresh_token, token_id = create_refresh_token(user_id)

    await redis_client.set(f"{REFRESH_TOKEN_PREFIX}:{token_id}",str(user_id),ex=settings.refresh_token_expire_days * 24 * 60 * 60)
    return access_token, refresh_token


async def rotate_refresh_token(old_refresh_token: str) -> tuple[str, str]:
    payload = decode_token(old_refresh_token)

    if payload.get("type") != "refresh":
        raise ValueError("Token is not a refresh token")

    token_id = payload["jti"]
    user_id = payload["sub"]

    stored_user_id = await redis_client.get(f"{REFRESH_TOKEN_PREFIX}:{token_id}")

    if stored_user_id is None or stored_user_id != user_id:
        raise ValueError("Refresh token is invalid, expired, or already used")

    await redis_client.delete(f"{REFRESH_TOKEN_PREFIX}:{token_id}")
    return await issue_tokens(uuid.UUID(user_id))


async def revoke_refresh_token(refresh_token: str) -> None:
    payload = decode_token(refresh_token)
    token_id = payload.get("jti")
    if token_id:
        await redis_client.delete(f"{REFRESH_TOKEN_PREFIX}:{token_id}")


async def register_user(db: AsyncSession, email: str, password: str) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Email already registered")

    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[str, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        raise ValueError("Invalid email or password")

    return await issue_tokens(user.id)