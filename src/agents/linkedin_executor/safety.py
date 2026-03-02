"""Safety mechanisms for LinkedIn automation."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import pytz
import structlog

from src.core.config import settings
from src.core.rate_limiter import rate_limiter

logger = structlog.get_logger()


class CircuitBreaker:
    """Circuit breaker to stop operations on repeated failures."""

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_timeout: int = 3600,
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure: Optional[datetime] = None
        self.state = "closed"

    def record_success(self) -> None:
        """Record a successful operation."""
        if self.state == "half-open":
            self.state = "closed"
            self.failures = 0
            logger.info("circuit_breaker_closed")

    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failures += 1
        self.last_failure = datetime.utcnow()

        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                "circuit_breaker_open",
                failures=self.failures,
            )

    def can_proceed(self) -> bool:
        """Check if operations can proceed."""
        if self.state == "closed":
            return True

        if self.state == "open":
            if self.last_failure:
                elapsed = (datetime.utcnow() - self.last_failure).total_seconds()
                if elapsed > self.reset_timeout:
                    self.state = "half-open"
                    logger.info("circuit_breaker_half_open")
                    return True
            return False

        return True

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self.state = "closed"
        self.failures = 0
        self.last_failure = None
        logger.info("circuit_breaker_reset")


class SafetyManager:
    """Manages all safety checks for LinkedIn automation."""

    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        self._security_warnings = 0
        self._last_security_check: Optional[datetime] = None

    async def can_proceed(self) -> bool:
        """Check all safety conditions before proceeding."""
        if not self.circuit_breaker.can_proceed():
            logger.warning("safety_blocked_circuit_breaker")
            return False

        if not rate_limiter.is_send_time():
            next_window = rate_limiter.get_next_optimal_window()
            logger.info(
                "safety_blocked_outside_optimal_window",
                next_window=next_window.isoformat(),
                is_optimal=rate_limiter.is_optimal_window(),
            )
            return False

        if not await rate_limiter.check_limit("connections"):
            logger.info("safety_blocked_rate_limit")
            return False

        if self._security_warnings >= 2:
            logger.warning("safety_blocked_security_warnings")
            return False

        return True

    def record_security_warning(self) -> None:
        """Record a security warning from LinkedIn."""
        self._security_warnings += 1
        self._last_security_check = datetime.utcnow()

        logger.warning(
            "security_warning_recorded",
            count=self._security_warnings,
        )

        if self._security_warnings >= 2:
            self.circuit_breaker.state = "open"
            logger.critical("safety_shutdown_security_warnings")

    def record_success(self) -> None:
        """Record a successful operation."""
        self.circuit_breaker.record_success()

    def record_failure(self, error: str) -> None:
        """Record a failed operation."""
        if "checkpoint" in error.lower() or "security" in error.lower():
            self.record_security_warning()
        else:
            self.circuit_breaker.record_failure()

    def reset_daily(self) -> None:
        """Reset daily counters (should be called at midnight)."""
        self._security_warnings = 0
        logger.info("safety_daily_reset")

    def get_status(self) -> dict:
        """Get current safety status."""
        return {
            "circuit_breaker_state": self.circuit_breaker.state,
            "circuit_breaker_failures": self.circuit_breaker.failures,
            "security_warnings": self._security_warnings,
            "is_working_hours": rate_limiter.is_working_hours(),
            "is_optimal_window": rate_limiter.is_optimal_window(),
            "is_send_time": rate_limiter.is_send_time(),
            "next_optimal_window": rate_limiter.get_next_optimal_window().isoformat(),
            "can_proceed": self.circuit_breaker.can_proceed(),
        }


async def exponential_backoff(
    attempt: int,
    base_delay: float = 2.0,
    max_delay: float = 300.0,
) -> None:
    """Wait with exponential backoff."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    logger.info("exponential_backoff", attempt=attempt, delay=delay)
    await asyncio.sleep(delay)


def is_safe_to_proceed() -> bool:
    """Quick check if it's safe to proceed with automation.
    
    Uses optimal windows when enabled:
    - Morning Rush: 8 AM - 10 AM PST
    - Afternoon Boost: 2 PM - 4 PM PST
    """
    return rate_limiter.is_send_time()


def get_next_safe_window() -> datetime:
    """Get the next optimal time window for automation.
    
    Returns the next time when recruiters/HMs are most active:
    - Morning Rush: 8 AM - 10 AM PST
    - Afternoon Boost: 2 PM - 4 PM PST
    """
    return rate_limiter.get_next_optimal_window()
