"""Tests for FastAPI endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock

from src.api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        with patch("src.api.main.rate_limiter.get_status", new_callable=AsyncMock) as mock:
            mock.return_value = {
                "connections_used": 0,
                "connections_limit": 20,
                "connections_remaining": 20,
                "is_working_hours": True,
                "resets_at": "2024-01-01T00:00:00",
                "current_time": "2024-01-01T12:00:00",
            }

            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_job_discovery_endpoint():
    """Test job discovery trigger endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/jobs/discover",
            json={
                "query": "ML Engineer",
                "location": "San Francisco",
                "sources": ["greenhouse"],
                "max_results": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "task_id" in data
