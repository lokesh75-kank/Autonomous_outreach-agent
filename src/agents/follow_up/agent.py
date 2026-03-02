"""Follow-up Agent for managing automated follow-ups."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import and_, select, update

from src.core.config import settings
from src.core.database import get_db_context
from src.models.db_models import (
    FollowUp,
    FollowUpStatus,
    FollowUpType,
    HiringManager,
    Job,
    OutreachQueue,
    OutreachStatus,
)

logger = structlog.get_logger()


class FollowUpAgent:
    """Agent for managing follow-ups and connection status."""

    def __init__(self):
        self.followup_day_1 = settings.followup_day_1
        self.followup_day_2 = settings.followup_day_2
        self.cold_after_days = settings.cold_after_days

    async def schedule_followups(self) -> Dict[str, Any]:
        """Schedule follow-ups for sent connections that need them."""
        scheduled = 0

        async with get_db_context() as db:
            day_1_threshold = datetime.utcnow() - timedelta(days=self.followup_day_1)
            day_2_threshold = datetime.utcnow() - timedelta(days=self.followup_day_2)

            result = await db.execute(
                select(OutreachQueue)
                .where(
                    OutreachQueue.status == OutreachStatus.SENT,
                    OutreachQueue.sent_at <= day_1_threshold,
                )
            )
            sent_outreach = result.scalars().all()

            for outreach in sent_outreach:
                existing = await db.execute(
                    select(FollowUp).where(
                        FollowUp.outreach_id == outreach.id,
                        FollowUp.type == FollowUpType.FOLLOW_UP_1,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                follow_up = FollowUp(
                    outreach_id=outreach.id,
                    type=FollowUpType.FOLLOW_UP_1,
                    scheduled_for=datetime.utcnow(),
                    status=FollowUpStatus.PENDING,
                )
                db.add(follow_up)
                scheduled += 1

            await db.commit()

        logger.info("followups_scheduled", count=scheduled)
        return {"scheduled": scheduled}

    async def process_pending(self) -> Dict[str, Any]:
        """Process all pending follow-ups."""
        from src.agents.personalization import PersonalizationEngine

        processed = 0
        errors = []

        personalization = PersonalizationEngine()

        async with get_db_context() as db:
            result = await db.execute(
                select(FollowUp)
                .where(
                    FollowUp.status == FollowUpStatus.PENDING,
                    FollowUp.scheduled_for <= datetime.utcnow(),
                )
                .order_by(FollowUp.scheduled_for)
                .limit(20)
            )
            pending = result.scalars().all()

        for follow_up in pending:
            try:
                message = await personalization.generate_follow_up(
                    follow_up.outreach_id,
                    follow_up.type,
                )

                if message:
                    async with get_db_context() as db:
                        await db.execute(
                            update(FollowUp)
                            .where(FollowUp.id == follow_up.id)
                            .values(
                                message=message,
                                status=FollowUpStatus.PENDING,
                            )
                        )
                        await db.commit()

                    processed += 1
                    logger.info(
                        "followup_message_generated",
                        followup_id=follow_up.id,
                    )
                else:
                    errors.append(f"Failed to generate message for {follow_up.id}")

            except Exception as e:
                logger.error(
                    "followup_process_error",
                    followup_id=follow_up.id,
                    error=str(e),
                )
                errors.append(str(e))

        return {"processed": processed, "errors": errors}

    async def check_status(self) -> Dict[str, Any]:
        """Check and update connection statuses."""
        updated = 0

        async with get_db_context() as db:
            cold_threshold = datetime.utcnow() - timedelta(days=self.cold_after_days)

            result = await db.execute(
                select(OutreachQueue)
                .where(
                    OutreachQueue.status == OutreachStatus.SENT,
                    OutreachQueue.sent_at <= cold_threshold,
                )
            )
            old_sent = result.scalars().all()

            for outreach in old_sent:
                existing_followups = await db.execute(
                    select(FollowUp).where(
                        FollowUp.outreach_id == outreach.id,
                        FollowUp.status == FollowUpStatus.PENDING,
                    )
                )
                pending_followups = existing_followups.scalars().all()

                for fu in pending_followups:
                    await db.execute(
                        update(FollowUp)
                        .where(FollowUp.id == fu.id)
                        .values(status=FollowUpStatus.CANCELLED)
                    )

                await db.execute(
                    update(OutreachQueue)
                    .where(OutreachQueue.id == outreach.id)
                    .values(status=OutreachStatus.COLD)
                )
                updated += 1

            await db.commit()

        logger.info("status_check_complete", marked_cold=updated)
        return {"marked_cold": updated}

    async def mark_accepted(self, outreach_id: str) -> Dict[str, Any]:
        """Mark a connection as accepted and schedule thank you."""
        async with get_db_context() as db:
            await db.execute(
                update(OutreachQueue)
                .where(OutreachQueue.id == outreach_id)
                .values(
                    status=OutreachStatus.ACCEPTED,
                    accepted_at=datetime.utcnow(),
                )
            )

            await db.execute(
                update(FollowUp)
                .where(
                    FollowUp.outreach_id == outreach_id,
                    FollowUp.status == FollowUpStatus.PENDING,
                )
                .values(status=FollowUpStatus.CANCELLED)
            )

            thank_you = FollowUp(
                outreach_id=outreach_id,
                type=FollowUpType.THANK_YOU,
                scheduled_for=datetime.utcnow(),
                status=FollowUpStatus.PENDING,
            )
            db.add(thank_you)

            await db.commit()

        logger.info("connection_accepted", outreach_id=outreach_id)
        return {"status": "accepted", "thank_you_scheduled": True}

    async def mark_replied(self, outreach_id: str) -> Dict[str, Any]:
        """Mark a connection as replied and notify user."""
        async with get_db_context() as db:
            await db.execute(
                update(OutreachQueue)
                .where(OutreachQueue.id == outreach_id)
                .values(
                    status=OutreachStatus.REPLIED,
                    replied_at=datetime.utcnow(),
                )
            )

            await db.execute(
                update(FollowUp)
                .where(
                    FollowUp.outreach_id == outreach_id,
                    FollowUp.status == FollowUpStatus.PENDING,
                )
                .values(status=FollowUpStatus.CANCELLED)
            )

            await db.commit()

        await self._notify_user(outreach_id)

        logger.info("connection_replied", outreach_id=outreach_id)
        return {"status": "replied", "user_notified": True}

    async def _notify_user(self, outreach_id: str) -> None:
        """Send notification to user about reply."""
        async with get_db_context() as db:
            result = await db.execute(
                select(OutreachQueue, Job, HiringManager)
                .join(Job)
                .join(HiringManager)
                .where(OutreachQueue.id == outreach_id)
            )
            row = result.first()

            if not row:
                return

            outreach, job, hm = row

        logger.info(
            "user_notification",
            company=job.company,
            role=job.role,
            hiring_manager=hm.name,
            message="Reply received - manual follow-up needed",
        )

    async def get_pending_followups(
        self, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get list of pending follow-ups with details."""
        async with get_db_context() as db:
            result = await db.execute(
                select(FollowUp, OutreachQueue, Job, HiringManager)
                .join(OutreachQueue)
                .join(Job, OutreachQueue.job_id == Job.id)
                .join(HiringManager, OutreachQueue.hiring_manager_id == HiringManager.id)
                .where(FollowUp.status == FollowUpStatus.PENDING)
                .order_by(FollowUp.scheduled_for)
                .limit(limit)
            )
            rows = result.all()

        return [
            {
                "followup_id": fu.id,
                "type": fu.type,
                "scheduled_for": fu.scheduled_for.isoformat(),
                "message": fu.message,
                "company": job.company,
                "role": job.role,
                "hiring_manager": hm.name,
            }
            for fu, outreach, job, hm in rows
        ]

    async def get_stats(self) -> Dict[str, Any]:
        """Get follow-up statistics."""
        async with get_db_context() as db:
            pending = await db.scalar(
                select(func.count(FollowUp.id)).where(
                    FollowUp.status == FollowUpStatus.PENDING
                )
            )

            sent = await db.scalar(
                select(func.count(FollowUp.id)).where(
                    FollowUp.status == FollowUpStatus.SENT
                )
            )

            accepted = await db.scalar(
                select(func.count(OutreachQueue.id)).where(
                    OutreachQueue.status == OutreachStatus.ACCEPTED
                )
            )

            replied = await db.scalar(
                select(func.count(OutreachQueue.id)).where(
                    OutreachQueue.status == OutreachStatus.REPLIED
                )
            )

            cold = await db.scalar(
                select(func.count(OutreachQueue.id)).where(
                    OutreachQueue.status == OutreachStatus.COLD
                )
            )

        return {
            "pending_followups": pending or 0,
            "sent_followups": sent or 0,
            "accepted_connections": accepted or 0,
            "replied_connections": replied or 0,
            "cold_connections": cold or 0,
        }


try:
    from sqlalchemy import func
except ImportError:
    pass
