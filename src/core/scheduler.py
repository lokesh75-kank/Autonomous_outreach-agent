"""Job scheduler for automated tasks."""

import asyncio
from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .rate_limiter import rate_limiter

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()


async def process_followups() -> None:
    """Process pending follow-ups."""
    from src.agents.follow_up.agent import FollowUpAgent

    logger.info("scheduler_followup_start")
    try:
        agent = FollowUpAgent()
        await agent.process_pending()
        logger.info("scheduler_followup_complete")
    except Exception as e:
        logger.error("scheduler_followup_error", error=str(e))


async def execute_approved_outreach() -> None:
    """Execute approved outreach requests during optimal windows.
    
    Optimal windows (PST):
    - Morning Rush: 8 AM - 10 AM (recruiters checking messages)
    - Afternoon Boost: 2 PM - 4 PM (final check before end of day)
    """
    from src.agents.linkedin_executor.agent import LinkedInExecutorAgent

    if not rate_limiter.is_send_time():
        next_window = rate_limiter.get_next_optimal_window()
        logger.info(
            "scheduler_skip_outside_optimal_window",
            next_window=next_window.isoformat(),
            is_optimal=rate_limiter.is_optimal_window(),
        )
        return

    remaining = await rate_limiter.get_remaining("connections")
    if remaining <= 0:
        logger.info("scheduler_skip_daily_limit")
        return

    logger.info(
        "scheduler_execute_start",
        remaining=remaining,
        window="morning" if rate_limiter.is_optimal_window() else "afternoon",
    )
    try:
        agent = LinkedInExecutorAgent()
        await agent.execute_batch(limit=min(5, remaining))
        logger.info("scheduler_execute_complete")
    except Exception as e:
        logger.error("scheduler_execute_error", error=str(e))


async def check_connection_status() -> None:
    """Check status of pending connections."""
    from src.agents.follow_up.agent import FollowUpAgent

    logger.info("scheduler_status_check_start")
    try:
        agent = FollowUpAgent()
        await agent.check_status()
        logger.info("scheduler_status_check_complete")
    except Exception as e:
        logger.error("scheduler_status_check_error", error=str(e))


def setup_scheduler() -> None:
    """Configure scheduled jobs.
    
    Outreach is scheduled during optimal windows when recruiters are most active:
    - Morning Rush: 8 AM - 10 AM PST
    - Afternoon Boost: 2 PM - 4 PM PST
    """
    scheduler.add_job(
        process_followups,
        CronTrigger(hour="*/2", minute=0),
        id="process_followups",
        replace_existing=True,
    )

    # Execute during optimal windows - every 15 minutes during peak hours
    # Morning window: 8:00, 8:15, 8:30, 8:45, 9:00, 9:15, 9:30, 9:45
    scheduler.add_job(
        execute_approved_outreach,
        CronTrigger(hour="8-9", minute="*/15"),
        id="execute_outreach_morning",
        replace_existing=True,
    )

    # Afternoon window: 14:00, 14:15, 14:30, 14:45, 15:00, 15:15, 15:30, 15:45
    scheduler.add_job(
        execute_approved_outreach,
        CronTrigger(hour="14-15", minute="*/15"),
        id="execute_outreach_afternoon",
        replace_existing=True,
    )

    scheduler.add_job(
        check_connection_status,
        CronTrigger(hour=10, minute=0),
        id="check_status",
        replace_existing=True,
    )

    logger.info(
        "scheduler_configured",
        optimal_windows={
            "morning": "8:00-10:00 PST",
            "afternoon": "14:00-16:00 PST",
        },
    )


def start_scheduler() -> None:
    """Start the scheduler."""
    setup_scheduler()
    scheduler.start()
    logger.info("scheduler_started")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    scheduler.shutdown()
    logger.info("scheduler_stopped")


if __name__ == "__main__":
    import signal
    import sys

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    def signal_handler(signum, frame):
        logger.info("shutdown_signal_received")
        stop_scheduler()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("scheduler_main_start")
    start_scheduler()

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        stop_scheduler()
