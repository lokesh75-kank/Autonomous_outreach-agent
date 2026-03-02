"""Pytest fixtures for testing."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base
from src.models.db_models import Job, HiringManager, OutreachQueue, UserProfile


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def sample_job(db_session: AsyncSession) -> Job:
    """Create sample job for testing."""
    import hashlib

    job = Job(
        source="manual",
        url="https://example.com/jobs/ml-engineer",
        url_hash=hashlib.sha256(b"https://example.com/jobs/ml-engineer").hexdigest()[:64],
        company="Example Corp",
        role="ML Engineer",
        location="San Francisco, CA",
        description="Looking for an ML Engineer...",
        skills=["Python", "TensorFlow", "PyTorch"],
        status="new",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest_asyncio.fixture
async def sample_hiring_manager(
    db_session: AsyncSession, sample_job: Job
) -> HiringManager:
    """Create sample hiring manager for testing."""
    hm = HiringManager(
        job_id=sample_job.id,
        name="Jane Smith",
        title="ML Engineering Manager",
        linkedin_url="https://linkedin.com/in/janesmith",
        company="Example Corp",
        relevance_score=85,
        status="new",
    )
    db_session.add(hm)
    await db_session.commit()
    await db_session.refresh(hm)
    return hm


@pytest_asyncio.fixture
async def sample_user_profile(db_session: AsyncSession) -> UserProfile:
    """Create sample user profile for testing."""
    profile = UserProfile(
        name="Test User",
        email="test@example.com",
        resume_text="Experienced ML engineer with 5 years...",
        skills=["Python", "ML", "TensorFlow"],
        experience_summary="5+ years building ML systems...",
        is_active=True,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile
