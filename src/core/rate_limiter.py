"""Rate limiting for LinkedIn safety."""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Optional

import pytz
import structlog

from .config import settings

logger = structlog.get_logger()


class RateLimiter:
    """Thread-safe rate limiter for LinkedIn actions."""

    def __init__(self):
        self._counts: Dict[str, int] = {}
        self._last_reset: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def _maybe_reset(self) -> None:
        """Reset counters if it's a new day."""
        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)
        today = now.date()

        if self._last_reset is None or self._last_reset.date() < today:
            self._counts = {}
            self._last_reset = now
            logger.info("rate_limiter_reset", date=str(today))

    async def check_limit(self, action: str = "connections") -> bool:
        """Check if action is within rate limits."""
        async with self._lock:
            await self._maybe_reset()

            limits = {
                "connections": settings.max_connections_per_day,
                "profile_views": 100,
                "messages": 50,
                "searches": 200,
            }

            current = self._counts.get(action, 0)
            limit = limits.get(action, 50)

            if current >= limit:
                logger.warning(
                    "rate_limit_exceeded",
                    action=action,
                    current=current,
                    limit=limit,
                )
                return False

            return True

    async def record_action(self, action: str = "connections") -> None:
        """Record an action for rate limiting."""
        async with self._lock:
            await self._maybe_reset()
            self._counts[action] = self._counts.get(action, 0) + 1
            logger.info(
                "action_recorded",
                action=action,
                count=self._counts[action],
            )

    async def get_remaining(self, action: str = "connections") -> int:
        """Get remaining actions for today."""
        async with self._lock:
            await self._maybe_reset()

            limits = {
                "connections": settings.max_connections_per_day,
                "profile_views": 100,
                "messages": 50,
                "searches": 200,
            }

            current = self._counts.get(action, 0)
            limit = limits.get(action, 50)

            return max(0, limit - current)

    def is_working_hours(self) -> bool:
        """Check if current time is within working hours."""
        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)

        if now.weekday() >= 5:
            return False

        if now.hour < settings.working_hours_start:
            return False

        if now.hour >= settings.working_hours_end:
            return False

        return True

    def is_optimal_window(self) -> bool:
        """Check if current time is within optimal outreach windows.
        
        Recruiters/HMs are most active during:
        - Morning Rush: 8 AM - 10 AM PST (checking messages, reviewing applicants)
        - Afternoon Boost: 2 PM - 4 PM PST (final check before end of day)
        """
        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)

        if now.weekday() >= 5:
            return False

        in_morning = (
            settings.morning_window_start <= now.hour < settings.morning_window_end
        )
        in_afternoon = (
            settings.afternoon_window_start <= now.hour < settings.afternoon_window_end
        )

        return in_morning or in_afternoon

    def is_send_time(self) -> bool:
        """Check if it's a good time to send connection requests.
        
        Uses optimal windows when enabled, falls back to general working hours.
        """
        if settings.use_optimal_windows:
            return self.is_optimal_window()
        return self.is_working_hours()

    def get_next_optimal_window(self) -> datetime:
        """Get the next optimal time window for sending connections."""
        tz = pytz.timezone(settings.timezone)
        now = datetime.now(tz)

        windows_today = [
            (settings.morning_window_start, settings.morning_window_end),
            (settings.afternoon_window_start, settings.afternoon_window_end),
        ]

        for start_hour, end_hour in windows_today:
            if now.hour < start_hour:
                return now.replace(hour=start_hour, minute=0, second=0, microsecond=0)

        tomorrow = now + timedelta(days=1)
        if tomorrow.weekday() >= 5:
            days_until_monday = 7 - tomorrow.weekday()
            tomorrow = tomorrow + timedelta(days=days_until_monday)

        return tomorrow.replace(
            hour=settings.morning_window_start,
            minute=0,
            second=0,
            microsecond=0,
        )

    async def get_status(self) -> dict:
        """Get current rate limiter status."""
        async with self._lock:
            await self._maybe_reset()

            tz = pytz.timezone(settings.timezone)
            now = datetime.now(tz)
            tomorrow = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            return {
                "connections_used": self._counts.get("connections", 0),
                "connections_limit": settings.max_connections_per_day,
                "connections_remaining": await self.get_remaining("connections"),
                "is_working_hours": self.is_working_hours(),
                "is_optimal_window": self.is_optimal_window(),
                "is_send_time": self.is_send_time(),
                "next_optimal_window": self.get_next_optimal_window().isoformat(),
                "optimal_windows": {
                    "morning": f"{settings.morning_window_start}:00-{settings.morning_window_end}:00",
                    "afternoon": f"{settings.afternoon_window_start}:00-{settings.afternoon_window_end}:00",
                },
                "resets_at": tomorrow.isoformat(),
                "current_time": now.isoformat(),
            }


async def random_delay(
    min_seconds: Optional[int] = None, max_seconds: Optional[int] = None
) -> None:
    """Wait for a random duration to simulate human behavior."""
    min_sec = min_seconds or settings.min_delay_seconds
    max_sec = max_seconds or settings.max_delay_seconds
    delay = random.uniform(min_sec, max_sec)
    logger.debug("random_delay", seconds=round(delay, 2))
    await asyncio.sleep(delay)


rate_limiter = RateLimiter()
