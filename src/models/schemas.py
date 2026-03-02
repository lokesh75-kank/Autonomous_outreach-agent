"""Pydantic schemas for API validation."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class JobBase(BaseModel):
    """Base job schema."""

    company: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., max_length=2048)
    location: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    skills: Optional[List[str]] = None
    salary_range: Optional[str] = Field(None, max_length=100)


class JobCreate(JobBase):
    """Schema for creating a job."""

    source: str = "manual"
    external_id: Optional[str] = None
    posted_date: Optional[datetime] = None


class JobResponse(JobBase):
    """Schema for job response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    status: str
    discovered_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    """Schema for job list response."""

    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int


class HiringManagerBase(BaseModel):
    """Base hiring manager schema."""

    name: str = Field(..., min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    linkedin_url: str = Field(..., max_length=2048)
    company: Optional[str] = Field(None, max_length=255)
    relevance_score: int = Field(default=50, ge=0, le=100)


class HiringManagerCreate(HiringManagerBase):
    """Schema for creating a hiring manager."""

    job_id: str


class HiringManagerResponse(HiringManagerBase):
    """Schema for hiring manager response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    status: str
    discovered_at: datetime


class OutreachBase(BaseModel):
    """Base outreach schema."""

    message: Optional[str] = Field(None, max_length=300)


class OutreachCreate(OutreachBase):
    """Schema for creating outreach."""

    job_id: str
    hiring_manager_id: str


class OutreachResponse(OutreachBase):
    """Schema for outreach response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    hiring_manager_id: str
    status: str
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class OutreachQueueItem(BaseModel):
    """Schema for outreach queue item with full details."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job: JobResponse
    hiring_manager: HiringManagerResponse
    message: Optional[str] = None
    status: str
    created_at: datetime


class OutreachQueueResponse(BaseModel):
    """Schema for outreach queue response."""

    queue: List[OutreachQueueItem]
    total: int


class ApproveOutreachRequest(BaseModel):
    """Schema for approving outreach."""

    message: Optional[str] = Field(None, max_length=300)


class RejectOutreachRequest(BaseModel):
    """Schema for rejecting outreach."""

    reason: Optional[str] = None


class BulkApproveRequest(BaseModel):
    """Schema for bulk approval."""

    outreach_ids: List[str]
    limit: Optional[int] = Field(default=20, le=50)


class FollowUpBase(BaseModel):
    """Base follow-up schema."""

    type: str
    message: Optional[str] = None
    scheduled_for: datetime


class FollowUpCreate(FollowUpBase):
    """Schema for creating follow-up."""

    outreach_id: str


class FollowUpResponse(FollowUpBase):
    """Schema for follow-up response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    outreach_id: str
    status: str
    completed_at: Optional[datetime] = None
    created_at: datetime


class UserProfileBase(BaseModel):
    """Base user profile schema."""

    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    resume_text: Optional[str] = None
    linkedin_url: Optional[str] = Field(None, max_length=2048)
    target_roles: Optional[List[str]] = None
    target_locations: Optional[List[str]] = None
    target_companies: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    experience_summary: Optional[str] = None


class UserProfileCreate(UserProfileBase):
    """Schema for creating user profile."""

    pass


class UserProfileResponse(UserProfileBase):
    """Schema for user profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobDiscoveryRequest(BaseModel):
    """Schema for job discovery request."""

    query: str = Field(..., min_length=1)
    location: Optional[str] = None
    sources: List[str] = Field(
        default=["jobright", "greenhouse", "lever"]
    )
    max_results: int = Field(default=50, le=200)


class JobDiscoveryResponse(BaseModel):
    """Schema for job discovery response."""

    status: str
    task_id: str
    message: str


class GenerateMessageRequest(BaseModel):
    """Schema for message generation request."""

    job_id: str
    hiring_manager_id: str


class ExecuteOutreachResponse(BaseModel):
    """Schema for execute outreach response."""

    status: str
    task_id: str
    pending_count: int
    message: str


class DashboardStats(BaseModel):
    """Schema for dashboard statistics."""

    jobs_discovered: int
    hiring_managers_found: int
    messages_generated: int
    connections_sent: int
    connections_accepted: int
    response_rate: float
    daily_limit_remaining: int
    today_sent: int


class RateLimiterStatus(BaseModel):
    """Schema for rate limiter status."""

    connections_used: int
    connections_limit: int
    connections_remaining: int
    is_working_hours: bool
    resets_at: str
    current_time: str


class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str
    database: str
    browser: str
    rate_limiter: RateLimiterStatus
