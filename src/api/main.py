"""FastAPI application main entry point."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db, init_db
from src.core.rate_limiter import rate_limiter
from src.models.db_models import (
    HiringManager,
    Job,
    JobStatus,
    OutreachQueue,
    OutreachStatus,
    UserProfile,
)
from src.models.schemas import (
    ApproveOutreachRequest,
    BulkApproveRequest,
    DashboardStats,
    ExecuteOutreachResponse,
    GenerateMessageRequest,
    HealthResponse,
    HiringManagerResponse,
    JobDiscoveryRequest,
    JobDiscoveryResponse,
    JobListResponse,
    JobResponse,
    OutreachQueueItem,
    OutreachQueueResponse,
    OutreachResponse,
    RateLimiterStatus,
    RejectOutreachRequest,
    UserProfileCreate,
    UserProfileResponse,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("application_startup")
    await init_db()
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title="AI Job Outreach Agent API",
    description="API for autonomous job discovery and LinkedIn outreach",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def run_job_discovery(request: JobDiscoveryRequest) -> None:
    """Background task for job discovery."""
    from src.agents.job_discovery import JobDiscoveryAgent

    agent = JobDiscoveryAgent()
    await agent.discover(
        query=request.query,
        location=request.location,
        sources=request.sources,
        max_results=request.max_results,
    )


async def run_hiring_manager_discovery(job_id: str) -> None:
    """Background task for hiring manager discovery."""
    from src.agents.hiring_manager import HiringManagerAgent

    agent = HiringManagerAgent()
    await agent.discover(job_id)


async def run_message_generation(job_id: str, hiring_manager_id: str) -> None:
    """Background task for message generation."""
    from src.agents.personalization import PersonalizationEngine

    engine = PersonalizationEngine()
    await engine.generate(job_id, hiring_manager_id)


async def run_outreach_execution() -> None:
    """Background task for outreach execution."""
    from src.agents.linkedin_executor import LinkedInExecutorAgent

    agent = LinkedInExecutorAgent()
    await agent.execute_batch(limit=5)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    rate_status = await rate_limiter.get_status()

    return HealthResponse(
        status="healthy",
        database="connected",
        browser="ready",
        rate_limiter=RateLimiterStatus(**rate_status),
    )


@app.post("/jobs/discover", response_model=JobDiscoveryResponse)
async def discover_jobs(
    request: JobDiscoveryRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger job discovery."""
    task_id = str(uuid.uuid4())

    background_tasks.add_task(run_job_discovery, request)

    logger.info(
        "job_discovery_triggered",
        task_id=task_id,
        query=request.query,
    )

    return JobDiscoveryResponse(
        status="started",
        task_id=task_id,
        message=f"Job discovery started for '{request.query}'",
    )


@app.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List discovered jobs."""
    query = select(Job)

    if status:
        query = query.where(Job.status == status)

    query = query.order_by(Job.discovered_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    jobs = result.scalars().all()

    count_query = select(func.count(Job.id))
    if status:
        count_query = count_query.where(Job.status == status)
    total = await db.scalar(count_query) or 0

    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get job details."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse.model_validate(job)


@app.post("/hiring-managers/discover/{job_id}")
async def discover_hiring_managers(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Discover hiring managers for a job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    background_tasks.add_task(run_hiring_manager_discovery, job_id)

    return {
        "status": "started",
        "job_id": job_id,
        "message": f"Hiring manager discovery started for {job.company} - {job.role}",
    }


@app.get("/hiring-managers")
async def list_hiring_managers(
    job_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List hiring managers."""
    query = select(HiringManager)

    if job_id:
        query = query.where(HiringManager.job_id == job_id)

    query = (
        query.order_by(HiringManager.relevance_score.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    hiring_managers = result.scalars().all()

    return {
        "hiring_managers": [
            HiringManagerResponse.model_validate(hm) for hm in hiring_managers
        ]
    }


@app.post("/outreach/generate")
async def generate_message(
    request: GenerateMessageRequest,
    background_tasks: BackgroundTasks,
):
    """Generate personalized message."""
    background_tasks.add_task(
        run_message_generation,
        request.job_id,
        request.hiring_manager_id,
    )

    return {
        "status": "started",
        "message": "Message generation started",
    }


@app.post("/outreach/generate-all")
async def generate_all_messages(
    limit: int = Query(default=20, le=50),
    background_tasks: BackgroundTasks = None,
):
    """Generate messages for all pending hiring managers."""
    from src.agents.personalization import PersonalizationEngine

    engine = PersonalizationEngine()
    result = await engine.generate_for_all_pending(limit=limit)

    return {
        "status": "completed",
        "generated": result["generated_count"],
        "errors": result["errors"],
    }


@app.get("/outreach/queue", response_model=OutreachQueueResponse)
async def get_outreach_queue(
    status: str = Query(default="pending_approval"),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get outreach approval queue."""
    result = await db.execute(
        select(OutreachQueue, Job, HiringManager)
        .join(Job)
        .join(HiringManager)
        .where(OutreachQueue.status == status)
        .order_by(OutreachQueue.created_at.desc())
        .limit(limit)
    )
    rows = result.all()

    queue = []
    for outreach, job, hm in rows:
        queue.append(
            OutreachQueueItem(
                id=outreach.id,
                job=JobResponse.model_validate(job),
                hiring_manager=HiringManagerResponse.model_validate(hm),
                message=outreach.message,
                status=outreach.status,
                created_at=outreach.created_at,
            )
        )

    count = await db.scalar(
        select(func.count(OutreachQueue.id)).where(
            OutreachQueue.status == status
        )
    )

    return OutreachQueueResponse(queue=queue, total=count or 0)


@app.post("/outreach/approve/{outreach_id}")
async def approve_outreach(
    outreach_id: str,
    request: Optional[ApproveOutreachRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Approve an outreach request."""
    result = await db.execute(
        select(OutreachQueue).where(OutreachQueue.id == outreach_id)
    )
    outreach = result.scalar_one_or_none()

    if not outreach:
        raise HTTPException(status_code=404, detail="Outreach not found")

    values = {"status": OutreachStatus.APPROVED}
    if request and request.message:
        values["message"] = request.message

    await db.execute(
        update(OutreachQueue)
        .where(OutreachQueue.id == outreach_id)
        .values(**values)
    )
    await db.commit()

    return {"status": "approved", "outreach_id": outreach_id}


@app.post("/outreach/reject/{outreach_id}")
async def reject_outreach(
    outreach_id: str,
    request: Optional[RejectOutreachRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Reject an outreach request."""
    result = await db.execute(
        select(OutreachQueue).where(OutreachQueue.id == outreach_id)
    )
    outreach = result.scalar_one_or_none()

    if not outreach:
        raise HTTPException(status_code=404, detail="Outreach not found")

    values = {"status": OutreachStatus.REJECTED}
    if request and request.reason:
        values["rejection_reason"] = request.reason

    await db.execute(
        update(OutreachQueue)
        .where(OutreachQueue.id == outreach_id)
        .values(**values)
    )
    await db.commit()

    return {"status": "rejected", "outreach_id": outreach_id}


@app.post("/outreach/bulk-approve")
async def bulk_approve_outreach(
    request: BulkApproveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bulk approve outreach requests."""
    approved = 0

    for outreach_id in request.outreach_ids[: request.limit]:
        result = await db.execute(
            select(OutreachQueue).where(
                OutreachQueue.id == outreach_id,
                OutreachQueue.status == OutreachStatus.PENDING_APPROVAL,
            )
        )
        outreach = result.scalar_one_or_none()

        if outreach:
            await db.execute(
                update(OutreachQueue)
                .where(OutreachQueue.id == outreach_id)
                .values(status=OutreachStatus.APPROVED)
            )
            approved += 1

    await db.commit()

    return {"approved": approved, "total_requested": len(request.outreach_ids)}


@app.post("/outreach/execute", response_model=ExecuteOutreachResponse)
async def execute_outreach(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Execute approved outreach."""
    if not rate_limiter.is_working_hours():
        raise HTTPException(
            status_code=503,
            detail="Outside working hours - execution disabled for safety",
        )

    remaining = await rate_limiter.get_remaining("connections")
    if remaining <= 0:
        raise HTTPException(
            status_code=429,
            detail="Daily connection limit reached",
        )

    count = await db.scalar(
        select(func.count(OutreachQueue.id)).where(
            OutreachQueue.status == OutreachStatus.APPROVED
        )
    )

    if not count:
        return ExecuteOutreachResponse(
            status="no_pending",
            task_id="",
            pending_count=0,
            message="No approved outreach to execute",
        )

    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_outreach_execution)

    return ExecuteOutreachResponse(
        status="started",
        task_id=task_id,
        pending_count=count,
        message=f"Execution started for {count} approved outreach (respecting limits)",
    )


@app.get("/stats/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics."""
    jobs = await db.scalar(select(func.count(Job.id))) or 0
    hiring_managers = await db.scalar(select(func.count(HiringManager.id))) or 0

    messages = await db.scalar(
        select(func.count(OutreachQueue.id)).where(
            OutreachQueue.message.isnot(None)
        )
    ) or 0

    sent = await db.scalar(
        select(func.count(OutreachQueue.id)).where(
            OutreachQueue.status.in_([
                OutreachStatus.SENT,
                OutreachStatus.ACCEPTED,
                OutreachStatus.REPLIED,
                OutreachStatus.COLD,
            ])
        )
    ) or 0

    accepted = await db.scalar(
        select(func.count(OutreachQueue.id)).where(
            OutreachQueue.status.in_([
                OutreachStatus.ACCEPTED,
                OutreachStatus.REPLIED,
            ])
        )
    ) or 0

    rate_status = await rate_limiter.get_status()
    today_sent = rate_status["connections_used"]

    response_rate = accepted / sent if sent > 0 else 0.0

    return DashboardStats(
        jobs_discovered=jobs,
        hiring_managers_found=hiring_managers,
        messages_generated=messages,
        connections_sent=sent,
        connections_accepted=accepted,
        response_rate=round(response_rate, 3),
        daily_limit_remaining=rate_status["connections_remaining"],
        today_sent=today_sent,
    )


@app.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    profile: UserProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """Update user profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.is_active == True).limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing:
        for key, value in profile.model_dump(exclude_unset=True).items():
            setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing)
        return UserProfileResponse.model_validate(existing)
    else:
        new_profile = UserProfile(**profile.model_dump())
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
        return UserProfileResponse.model_validate(new_profile)


@app.get("/profile", response_model=Optional[UserProfileResponse])
async def get_profile(
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.is_active == True).limit(1)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return None

    return UserProfileResponse.model_validate(profile)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
