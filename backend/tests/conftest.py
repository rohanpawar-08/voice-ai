import pytest
from app.core.database import AsyncSessionLocal


@pytest.fixture
async def db_session():
    """Provides a fresh database session per test function and closes it cleanly."""
    session = AsyncSessionLocal()
    yield session
    try:
        await session.close()
    except Exception:
        pass
