"""Greenhouse job board scraper."""

import asyncio
from typing import Any, Dict, List, Optional

import structlog

from .base import BaseScraper

logger = structlog.get_logger()


GREENHOUSE_COMPANIES = [
    "airbnb",
    "stripe",
    "notion",
    "figma",
    "discord",
    "plaid",
    "coinbase",
    "instacart",
    "doordash",
    "reddit",
    "scale",
    "anthropic",
    "openai",
    "databricks",
    "snowflake",
]


class GreenhouseScraper(BaseScraper):
    """Scraper for Greenhouse job boards."""

    source_name = "greenhouse"
    base_url = "https://boards-api.greenhouse.io/v1/boards"

    async def scrape(
        self,
        query: str,
        location: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from Greenhouse boards."""
        all_jobs = []
        query_lower = query.lower()

        tasks = [
            self._scrape_company(company, query_lower, location)
            for company in GREENHOUSE_COMPANIES
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for company, result in zip(GREENHOUSE_COMPANIES, results):
            if isinstance(result, Exception):
                logger.warning(
                    "greenhouse_company_error",
                    company=company,
                    error=str(result),
                )
            else:
                all_jobs.extend(result)

        all_jobs = all_jobs[:max_results]
        logger.info("greenhouse_scrape_complete", job_count=len(all_jobs))
        return all_jobs

    async def _scrape_company(
        self, company: str, query: str, location: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from a single company's Greenhouse board."""
        jobs = []

        try:
            url = f"{self.base_url}/{company}/jobs"
            data = await self.fetch_json(url)

            for job in data.get("jobs", []):
                title = job.get("title", "").lower()
                job_location = job.get("location", {}).get("name", "")

                if query not in title:
                    continue

                if location and location.lower() not in job_location.lower():
                    continue

                job_url = job.get("absolute_url", "")

                job_detail = await self._get_job_details(job_url, job.get("id"))

                jobs.append({
                    "source": self.source_name,
                    "external_id": str(job.get("id")),
                    "role": job.get("title"),
                    "company": company.title(),
                    "location": job_location,
                    "url": job_url,
                    "description": job_detail.get("description"),
                    "skills": job_detail.get("skills", []),
                })

        except Exception as e:
            logger.debug("greenhouse_company_skip", company=company, error=str(e))

        return jobs

    async def _get_job_details(
        self, job_url: str, job_id: Optional[int]
    ) -> Dict[str, Any]:
        """Get detailed job information."""
        try:
            if job_id:
                for company in GREENHOUSE_COMPANIES:
                    try:
                        url = f"{self.base_url}/{company}/jobs/{job_id}"
                        data = await self.fetch_json(url)
                        content = data.get("content", "")
                        return {
                            "description": self.clean_text(
                                BeautifulSoup(content, "lxml").get_text()
                            )[:3000],
                            "skills": self.extract_skills(content),
                        }
                    except Exception:
                        continue
        except Exception:
            pass

        return {"description": None, "skills": []}


try:
    from bs4 import BeautifulSoup
except ImportError:
    pass
