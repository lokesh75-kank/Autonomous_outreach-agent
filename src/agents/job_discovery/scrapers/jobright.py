"""Jobright job scraper."""

import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import structlog
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .base import BaseScraper

logger = structlog.get_logger()


class JobrightScraper(BaseScraper):
    """Scraper for Jobright.ai jobs."""

    source_name = "jobright"
    base_url = "https://jobright.ai"

    async def scrape(
        self,
        query: str,
        location: Optional[str] = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Scrape jobs from Jobright."""
        jobs = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                search_url = f"{self.base_url}/jobs?q={quote(query)}"
                if location:
                    search_url += f"&location={quote(location)}"

                await page.goto(search_url, wait_until="networkidle")
                await asyncio.sleep(3)

                content = await page.content()
                soup = BeautifulSoup(content, "lxml")

                job_cards = soup.select("div[class*='job-card'], article[class*='job']")

                for card in job_cards[:max_results]:
                    try:
                        job = self._parse_job_card(card)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.warning("parse_job_error", error=str(e))

                await browser.close()

        except Exception as e:
            logger.error("jobright_scrape_error", error=str(e))
            raise

        logger.info("jobright_scrape_complete", job_count=len(jobs))
        return jobs

    def _parse_job_card(self, card) -> Optional[Dict[str, Any]]:
        """Parse a job card element."""
        title_elem = card.select_one("h2, h3, [class*='title']")
        company_elem = card.select_one("[class*='company'], [class*='employer']")
        location_elem = card.select_one("[class*='location']")
        link_elem = card.select_one("a[href*='job']")

        if not title_elem or not company_elem or not link_elem:
            return None

        href = link_elem.get("href", "")
        if not href.startswith("http"):
            href = f"{self.base_url}{href}"

        description = card.get_text(separator=" ", strip=True)

        return {
            "source": self.source_name,
            "role": self.clean_text(title_elem.get_text()),
            "company": self.clean_text(company_elem.get_text()),
            "location": self.clean_text(location_elem.get_text()) if location_elem else None,
            "url": href,
            "description": description[:2000] if description else None,
            "skills": self.extract_skills(description) if description else [],
        }
