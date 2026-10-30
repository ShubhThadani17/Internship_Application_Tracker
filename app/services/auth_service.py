import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import redis_client
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.core.config import settings
from app.db.models import User
from jose import JWTError


REFRESH_TOKEN_PREFIX = "refresh_token"


async def issue_tokens(user_id: uuid.UUID) -> tuple[str, str]:
    access_token = create_access_token(user_id)
    refresh_token, token_id = create_refresh_token(user_id)

    await redis_client.set(f"{REFRESH_TOKEN_PREFIX}:{token_id}",str(user_id),ex=settings.refresh_token_expire_days * 24 * 60 * 60)
    return access_token, refresh_token


async def rotate_refresh_token(
    old_refresh_token: str,
) -> tuple[str, str]:

    # Decode the token safely.
    try:
        payload = decode_token(old_refresh_token)
    except JWTError as exc:
        raise ValueError(
            "Refresh token is invalid or expired"
        ) from exc

    # Validate token payload.
    if not isinstance(payload, dict):
        raise ValueError("Invalid refresh token")

    if payload.get("type") != "refresh":
        raise ValueError("Token is not a refresh token")

    token_id = payload.get("jti")
    user_id = payload.get("sub")

    if not token_id or not user_id:
        raise ValueError("Invalid refresh token")

    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid refresh token") from exc

    # Check whether the refresh token exists in Redis.
    stored_user_id = await redis_client.get(
        f"{REFRESH_TOKEN_PREFIX}:{token_id}"
    )

    if stored_user_id is None or stored_user_id != user_id:
        raise ValueError(
            "Refresh token is invalid, expired, or already used"
        )

    # Invalidate the old token.
    await redis_client.delete(
        f"{REFRESH_TOKEN_PREFIX}:{token_id}"
    )

    # Issue a fresh access and refresh token pair.
    return await issue_tokens(user_uuid)


async def revoke_refresh_token(refresh_token: str) -> None:

    try:
        payload = decode_token(refresh_token)

    except JWTError:
        # Invalid or expired token.
        # Logout is intentionally idempotent.
        return

    if not isinstance(payload, dict):
        return

    if payload.get("type") != "refresh":
        return

    token_id = payload.get("jti")

    if token_id:
        await redis_client.delete(
            f"{REFRESH_TOKEN_PREFIX}:{token_id}"
        )


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