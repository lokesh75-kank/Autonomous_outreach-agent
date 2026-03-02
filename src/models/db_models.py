"""SQLAlchemy database models."""

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from src.core.database import Base


class JobStatus(str, enum.Enum):
    NEW = "new"
    PROCESSED = "processed"
    EXPIRED = "expired"
    SKIPPED = "skipped"


class JobSource(str, enum.Enum):
    JOBRIGHT = "jobright"
    LINKEDIN = "linkedin"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    MANUAL = "manual"


class OutreachStatus(str, enum.Enum):
    PENDING_ENRICHMENT = "pending_enrichment"
    PENDING_MESSAGE = "pending_message"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    ACCEPTED = "accepted"
    REPLIED = "replied"
    COLD = "cold"
    ERROR = "error"


class FollowUpType(str, enum.Enum):
    FOLLOW_UP_1 = "follow_up_1"
    FOLLOW_UP_2 = "follow_up_2"
    THANK_YOU = "thank_you"
    RESUME = "resume"


class FollowUpStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    CANCELLED = "cancelled"


class Job(Base):
    """Job listing model."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    source: Mapped[str] = mapped_column(
        Enum(JobSource), default=JobSource.MANUAL
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    company: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(255))
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skills: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    salary_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    posted_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(JobStatus), default=JobStatus.NEW
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    hiring_managers: Mapped[List["HiringManager"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    outreach_queue: Mapped[List["OutreachQueue"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class HiringManager(Base):
    """Hiring manager / recruiter model."""

    __tablename__ = "hiring_managers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str] = mapped_column(String(2048))
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    relevance_score: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(50), default="new")
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    job: Mapped["Job"] = relationship(back_populates="hiring_managers")
    outreach_queue: Mapped[List["OutreachQueue"]] = relationship(
        back_populates="hiring_manager", cascade="all, delete-orphan"
    )


class OutreachQueue(Base):
    """Outreach queue for approval workflow."""

    __tablename__ = "outreach_queue"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    hiring_manager_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("hiring_managers.id", ondelete="CASCADE")
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(OutreachStatus), default=OutreachStatus.PENDING_MESSAGE
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    job: Mapped["Job"] = relationship(back_populates="outreach_queue")
    hiring_manager: Mapped["HiringManager"] = relationship(
        back_populates="outreach_queue"
    )
    logs: Mapped[List["OutreachLog"]] = relationship(
        back_populates="outreach", cascade="all, delete-orphan"
    )
    follow_ups: Mapped[List["FollowUp"]] = relationship(
        back_populates="outreach", cascade="all, delete-orphan"
    )


class OutreachLog(Base):
    """Log of outreach actions."""

    __tablename__ = "outreach_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    outreach_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("outreach_queue.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(50))
    result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    outreach: Mapped["OutreachQueue"] = relationship(back_populates="logs")


class FollowUp(Base):
    """Follow-up scheduling."""

    __tablename__ = "follow_ups"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    outreach_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("outreach_queue.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(Enum(FollowUpType))
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(
        Enum(FollowUpStatus), default=FollowUpStatus.PENDING
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    outreach: Mapped["OutreachQueue"] = relationship(back_populates="follow_ups")


class UserProfile(Base):
    """User profile for personalization."""

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resume_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    target_roles: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    target_locations: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    target_companies: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    skills: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    experience_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
