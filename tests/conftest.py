import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession 

from app.core.security import hash_password
from app.db.base import engine, AsyncSessionLocal
from app.db.models import User
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.base import get_db
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.sync_session import sync_engine



@pytest_asyncio.fixture
async def db():
    async with engine.connect() as connection:
        transaction = await connection.begin()

        session = AsyncSession(bind=connection, expire_on_commit=False)

        yield session

        await session.close()
        await transaction.rollback()


@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(email="test@example.com", hashed_password="fake_hash")
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def registered_user(db: AsyncSession) -> tuple[User, str]:
    plain_password = "correct-horse-battery-staple"
    user = User(
        email="registered@example.com",
        hashed_password=hash_password(plain_password),
    )
    db.add(user)
    await db.flush()
    return user, plain_password


@pytest_asyncio.fixture
async def client(db: AsyncSession):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    email = f"test-{uuid.uuid4()}@example.com"
    password = "strongpassword123"

    register_response = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def sync_db():
    connection = sync_engine.connect()
    transaction = connection.begin()

    session = Session(bind=connection, expire_on_commit=False)

    yield session

    session.close()
    transaction.rollback()
    connection.close()