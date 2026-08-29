from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from app.core.config import settings

DATABASE_URL = settings.database_url

engine = create_async_engine(DATABASE_URL, echo=True)

#You're creating a factory that creates AsyncSession objects.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,     #The sessions created by this factory should use this database engine.
    class_=AsyncSession,    #create an asynchronous session.
    expire_on_commit=False, 
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session