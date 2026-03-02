"""Lever job board scraper."""

import asyncio
from typing import Any, Dict, List, Optional

import structlog
from bs4 import BeautifulSoup

from .base import BaseScraper

logger = structlog.get_logger()


LEVER_COMPANIES = [
    "netflix",
    "lyft",
    "robinhood",
    "twitch",
    "cloudflare",
    "datadog",
    "atlassian",
    "figma",
    "airtable",
    "zapier",
    "gitlab",
    "hashicorp",
    "elastic",
    "mongodb",
    "confluent",
]


class LeverScraper(BaseScraper):
    """Scraper for Lever job boards."""

    source_name = "lever"
    base_url = "https://api.lever.co/v0/postings"

    async def scrape(
        self,
        query: str,
        location: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from Lever boards."""
        all_jobs = []
        query_lower = query.lower()

        tasks = [
            self._scrape_company(company, query_lower, location)
            for company in LEVER_COMPANIES
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for company, result in zip(LEVER_COMPANIES, results):
            if isinstance(result, Exception):
                logger.warning(
                    "lever_company_error",
                    company=company,
                    error=str(result),
                )
            else:
                all_jobs.extend(result)

        all_jobs = all_jobs[:max_results]
        logger.info("lever_scrape_complete", job_count=len(all_jobs))
        return all_jobs

    async def _scrape_company(
        self, company: str, query: str, location: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from a single company's Lever board."""
        jobs = []

        try:
            url = f"{self.base_url}/{company}?mode=json"
            data = await self.fetch_json(url)

            for job in data:
                title = job.get("text", "").lower()
                categories = job.get("categories", {})
                job_location = categories.get("location", "")

                if query not in title:
                    continue

                if location and location.lower() not in job_location.lower():
                    continue

                description_html = job.get("descriptionPlain", "") or job.get(
                    "description", ""
                )
                description = self.clean_text(
                    BeautifulSoup(description_html, "lxml").get_text()
                )[:3000]

                lists_html = job.get("lists", [])
                for lst in lists_html:
                    content = lst.get("content", "")
                    description += " " + self.clean_text(
                        BeautifulSoup(content, "lxml").get_text()
                    )

                jobs.append({
                    "source": self.source_name,
                    "external_id": job.get("id"),
                    "role": job.get("text"),
                    "company": company.title(),
                    "location": job_location,
                    "url": job.get("hostedUrl", f"https://jobs.lever.co/{company}/{job.get('id')}"),
                    "description": description[:3000],
                    "skills": self.extract_skills(description),
                })

        except Exception as e:
            logger.debug("lever_company_skip", company=company, error=str(e))

        return jobs
