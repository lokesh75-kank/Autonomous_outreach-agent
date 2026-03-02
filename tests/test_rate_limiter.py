"""Tests for rate limiter."""

import pytest
from unittest.mock import patch
from datetime import datetime

from src.core.rate_limiter import RateLimiter, random_delay


@pytest.mark.asyncio
async def test_rate_limiter_check_limit():
    """Test rate limiter allows actions within limit."""
    limiter = RateLimiter()

    assert await limiter.check_limit("connections") is True


@pytest.mark.asyncio
async def test_rate_limiter_record_action():
    """Test rate limiter records actions."""
    limiter = RateLimiter()

    await limiter.record_action("connections")
    remaining = await limiter.get_remaining("connections")

    assert remaining == 19


@pytest.mark.asyncio
async def test_rate_limiter_exceeds_limit():
    """Test rate limiter blocks when limit exceeded."""
    limiter = RateLimiter()
    limiter._counts["connections"] = 20

    assert await limiter.check_limit("connections") is False


@pytest.mark.asyncio
async def test_rate_limiter_status():
    """Test rate limiter status reporting."""
    limiter = RateLimiter()

    status = await limiter.get_status()

    assert "connections_used" in status
    assert "connections_limit" in status
    assert "connections_remaining" in status
    assert "is_working_hours" in status


def test_is_working_hours():
    """Test working hours check."""
    limiter = RateLimiter()

    result = limiter.is_working_hours()
    assert isinstance(result, bool)


def test_is_optimal_window():
    """Test optimal window check."""
    limiter = RateLimiter()

    result = limiter.is_optimal_window()
    assert isinstance(result, bool)


def test_is_send_time():
    """Test send time check (optimal windows or working hours)."""
    limiter = RateLimiter()

    result = limiter.is_send_time()
    assert isinstance(result, bool)


def test_get_next_optimal_window():
    """Test next optimal window calculation."""
    limiter = RateLimiter()

    result = limiter.get_next_optimal_window()
    assert result is not None
    assert hasattr(result, 'hour')


@pytest.mark.asyncio
async def test_random_delay():
    """Test random delay function."""
    import asyncio

    start = datetime.now()
    await random_delay(0.1, 0.2)
    elapsed = (datetime.now() - start).total_seconds()

    assert 0.1 <= elapsed <= 0.5
