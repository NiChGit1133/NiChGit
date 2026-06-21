"""Database connection setup for SQLite."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from ..config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dependency to get an async database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables."""
    from .models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
