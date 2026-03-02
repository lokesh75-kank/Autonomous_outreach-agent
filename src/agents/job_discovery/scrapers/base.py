"""Base scraper class for job boards."""

import asyncio
import random
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


class BaseScraper(ABC):
    """Base class for job scrapers."""

    source_name: str = "unknown"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    @abstractmethod
    async def scrape(
        self,
        query: str,
        location: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from the source."""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def fetch_url(self, url: str) -> httpx.Response:
        """Fetch a URL with retry logic."""
        await asyncio.sleep(random.uniform(1, 3))
        response = await self.client.get(url)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def fetch_json(self, url: str) -> Dict[str, Any]:
        """Fetch JSON from URL with retry logic."""
        await asyncio.sleep(random.uniform(1, 3))
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    def extract_skills(self, description: str) -> List[str]:
        """Extract skills from job description."""
        common_skills = [
            "python", "javascript", "typescript", "java", "c++", "go", "rust",
            "react", "vue", "angular", "node.js", "django", "flask", "fastapi",
            "aws", "gcp", "azure", "kubernetes", "docker", "terraform",
            "sql", "postgresql", "mongodb", "redis", "elasticsearch",
            "machine learning", "deep learning", "tensorflow", "pytorch",
            "data science", "spark", "hadoop", "kafka", "airflow",
            "ci/cd", "jenkins", "github actions", "git",
        ]

        description_lower = description.lower()
        found_skills = []

        for skill in common_skills:
            if skill in description_lower:
                found_skills.append(skill.title())

        return list(set(found_skills))[:15]

    def clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace."""
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()
