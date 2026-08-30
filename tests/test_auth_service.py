# tests/test_auth_service.py

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.redis_client import redis_client
from app.services.auth_service import (
    issue_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import redis_client
from app.db.models import User
from app.services.auth_service import (
    issue_tokens,
    login_user,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)


# ---------------------------------------------------------
# Mocked unit tests — verify logic and call shape in isolation
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_issue_tokens():
    user_id = uuid.uuid4()

    with (
        patch(
            "app.services.auth_service.create_access_token",
            return_value="access-token",
        ) as mock_access,
        patch(
            "app.services.auth_service.create_refresh_token",
            return_value=("refresh-token", "token-123"),
        ) as mock_refresh,
        patch(
            "app.services.auth_service.redis_client.set",
            new_callable=AsyncMock,
        ) as mock_redis_set,
    ):
        access_token, refresh_token = await issue_tokens(user_id)

    assert access_token == "access-token"
    assert refresh_token == "refresh-token"

    mock_access.assert_called_once_with(user_id)
    mock_refresh.assert_called_once_with(user_id)

    mock_redis_set.assert_awaited_once_with(
        "refresh_token:token-123",
        str(user_id),
        ex=7 * 24 * 60 * 60,
    )


@pytest.mark.asyncio
async def test_rotate_refresh_token():
    user_id = uuid.uuid4()
    old_token = "old-refresh-token"

    with (
        patch(
            "app.services.auth_service.decode_token",
            return_value={
                "type": "refresh",
                "jti": "old-token-id",
                "sub": str(user_id),
            },
        ),
        patch(
            "app.services.auth_service.redis_client.get",
            new_callable=AsyncMock,
            return_value=str(user_id),
        ) as mock_redis_get,
        patch(
            "app.services.auth_service.redis_client.delete",
            new_callable=AsyncMock,
        ) as mock_redis_delete,
        patch(
            "app.services.auth_service.issue_tokens",
            new_callable=AsyncMock,
            return_value=("new-access-token", "new-refresh-token"),
        ) as mock_issue_tokens,
    ):
        result = await rotate_refresh_token(old_token)

    assert result == ("new-access-token", "new-refresh-token")

    mock_redis_get.assert_awaited_once_with("refresh_token:old-token-id")
    mock_redis_delete.assert_awaited_once_with("refresh_token:old-token-id")
    mock_issue_tokens.assert_awaited_once_with(user_id)


@pytest.mark.asyncio
async def test_rotate_refresh_token_rejects_access_token():
    with patch(
        "app.services.auth_service.decode_token",
        return_value={
            "type": "access",
            "jti": "token-id",
            "sub": str(uuid.uuid4()),
        },
    ):
        with pytest.raises(ValueError, match="Token is not a refresh token"):
            await rotate_refresh_token("access-token")


@pytest.mark.asyncio
async def test_rotate_refresh_token_rejects_missing_redis_token():
    user_id = uuid.uuid4()

    with (
        patch(
            "app.services.auth_service.decode_token",
            return_value={
                "type": "refresh",
                "jti": "token-id",
                "sub": str(user_id),
            },
        ),
        patch(
            "app.services.auth_service.redis_client.get",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        with pytest.raises(
            ValueError,
            match="Refresh token is invalid, expired, or already used",
        ):
            await rotate_refresh_token("refresh-token")


@pytest.mark.asyncio
async def test_rotate_refresh_token_rejects_wrong_user():
    user_id = uuid.uuid4()
    different_user_id = uuid.uuid4()

    with (
        patch(
            "app.services.auth_service.decode_token",
            return_value={
                "type": "refresh",
                "jti": "token-id",
                "sub": str(user_id),
            },
        ),
        patch(
            "app.services.auth_service.redis_client.get",
            new_callable=AsyncMock,
            return_value=str(different_user_id),
        ),
    ):
        with pytest.raises(
            ValueError,
            match="Refresh token is invalid, expired, or already used",
        ):
            await rotate_refresh_token("refresh-token")


@pytest.mark.asyncio
async def test_rotate_refresh_token_deletes_old_token_before_issuing_new_tokens():
    user_id = uuid.uuid4()
    call_order = []

    async def track_delete(*args, **kwargs):
        call_order.append("delete")

    async def track_issue(*args, **kwargs):
        call_order.append("issue")
        return "new-access", "new-refresh"

    with (
        patch(
            "app.services.auth_service.decode_token",
            return_value={
                "type": "refresh",
                "jti": "old-token-id",
                "sub": str(user_id),
            },
        ),
        patch(
            "app.services.auth_service.redis_client.get",
            new_callable=AsyncMock,
            return_value=str(user_id),
        ),
        patch(
            "app.services.auth_service.redis_client.delete",
            side_effect=track_delete,
        ),
        patch(
            "app.services.auth_service.issue_tokens",
            side_effect=track_issue,
        ),
    ):
        await rotate_refresh_token("old-refresh")

    assert call_order == ["delete", "issue"]


@pytest.mark.asyncio
async def test_revoke_refresh_token():
    with (
        patch(
            "app.services.auth_service.decode_token",
            return_value={
                "type": "refresh",
                "jti": "token-id",
                "sub": str(uuid.uuid4()),
            },
        ),
        patch(
            "app.services.auth_service.redis_client.delete",
            new_callable=AsyncMock,
        ) as mock_delete,
    ):
        await revoke_refresh_token("refresh-token")

    mock_delete.assert_awaited_once_with("refresh_token:token-id")


@pytest.mark.asyncio
async def test_revoke_refresh_token_without_jti():
    with (
        patch(
            "app.services.auth_service.decode_token",
            return_value={
                "type": "refresh",
                "sub": str(uuid.uuid4()),
            },
        ),
        patch(
            "app.services.auth_service.redis_client.delete",
            new_callable=AsyncMock,
        ) as mock_delete,
    ):
        await revoke_refresh_token("refresh-token")

    mock_delete.assert_not_awaited()


# ---------------------------------------------------------
# Integration test — real Redis, no mocks
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_issue_and_rotate_against_real_redis():
    user_id = uuid.uuid4()
    created_keys = []

    try:
        access_token, refresh_token = await issue_tokens(user_id)

        new_access, new_refresh = await rotate_refresh_token(refresh_token)

        assert new_access != access_token
        assert new_refresh != refresh_token

        # old refresh token must now be rejected, proving rotation
        # actually invalidated it against real Redis
        with pytest.raises(ValueError):
            await rotate_refresh_token(refresh_token)

    finally:
        # clean up whatever refresh_token keys this test created,
        # since real Redis has no rollback like the Postgres tests do
        cursor = None
        async for key in redis_client.scan_iter(match="refresh_token:*"):
            created_keys.append(key)

        if created_keys:
            await redis_client.delete(*created_keys)

@pytest.mark.asyncio
async def test_register_user_creates_user(db: AsyncSession):
    user = await register_user(
        db=db, email="newuser@example.com", password="strongpassword123"
    )

    assert user.id is not None
    assert user.email == "newuser@example.com"
    assert user.hashed_password != "strongpassword123"


@pytest.mark.asyncio
async def test_register_user_rejects_duplicate_email(
    db: AsyncSession, test_user: User
):
    with pytest.raises(ValueError, match="Email already registered"):
        await register_user(
            db=db, email=test_user.email, password="anotherpassword"
        )


# ---------------------------------------------------------
# login_user — real Postgres, rollback isolated
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_login_user_success(
    db: AsyncSession, registered_user: tuple[User, str]
):
    user, plain_password = registered_user

    with patch(
        "app.services.auth_service.issue_tokens",
        new_callable=AsyncMock,
        return_value=("access-token", "refresh-token"),
    ) as mock_issue_tokens:
        access_token, refresh_token = await login_user(
            db=db, email=user.email, password=plain_password
        )

    assert access_token == "access-token"
    assert refresh_token == "refresh-token"
    mock_issue_tokens.assert_awaited_once_with(user.id)


@pytest.mark.asyncio
async def test_login_user_rejects_wrong_password(
    db: AsyncSession, registered_user: tuple[User, str]
):
    user, _ = registered_user

    with pytest.raises(ValueError, match="Invalid email or password"):
        await login_user(db=db, email=user.email, password="wrong-password")


@pytest.mark.asyncio
async def test_login_user_rejects_nonexistent_email(db: AsyncSession):
    with pytest.raises(ValueError, match="Invalid email or password"):
        await login_user(
            db=db, email="doesnotexist@example.com", password="whatever"
        )