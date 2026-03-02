"""Tests for database models and schemas."""

import pytest
from pydantic import ValidationError

from src.models.schemas import (
    JobCreate,
    JobResponse,
    HiringManagerCreate,
    OutreachCreate,
    UserProfileCreate,
)


def test_job_create_valid():
    """Test valid job creation."""
    job = JobCreate(
        company="Example Corp",
        role="ML Engineer",
        url="https://example.com/jobs/1",
        location="San Francisco",
        skills=["Python", "ML"],
    )

    assert job.company == "Example Corp"
    assert job.role == "ML Engineer"


def test_job_create_invalid_url():
    """Test job creation with empty company fails."""
    with pytest.raises(ValidationError):
        JobCreate(
            company="",
            role="ML Engineer",
            url="https://example.com/jobs/1",
        )


def test_hiring_manager_create():
    """Test hiring manager creation."""
    hm = HiringManagerCreate(
        job_id="test-uuid",
        name="Jane Smith",
        title="Engineering Manager",
        linkedin_url="https://linkedin.com/in/janesmith",
        relevance_score=85,
    )

    assert hm.name == "Jane Smith"
    assert hm.relevance_score == 85


def test_hiring_manager_relevance_score_bounds():
    """Test relevance score must be 0-100."""
    with pytest.raises(ValidationError):
        HiringManagerCreate(
            job_id="test-uuid",
            name="Jane Smith",
            linkedin_url="https://linkedin.com/in/janesmith",
            relevance_score=150,
        )


def test_user_profile_create():
    """Test user profile creation."""
    profile = UserProfileCreate(
        name="Test User",
        email="test@example.com",
        resume_text="Experienced engineer...",
        target_roles=["ML Engineer", "Data Scientist"],
        skills=["Python", "TensorFlow"],
    )

    assert profile.name == "Test User"
    assert len(profile.target_roles) == 2


def test_outreach_message_length():
    """Test outreach message max length."""
    outreach = OutreachCreate(
        job_id="job-uuid",
        hiring_manager_id="hm-uuid",
        message="Hi there! " * 30,
    )

    assert len(outreach.message) <= 300
