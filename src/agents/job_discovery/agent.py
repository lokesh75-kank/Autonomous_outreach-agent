"""Job Discovery Agent using LangGraph for orchestration."""

import asyncio
import hashlib
from typing import Any, Dict, List, Optional, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from src.core.database import get_db_context
from src.models.db_models import Job, JobSource, JobStatus
from src.models.schemas import JobCreate

from .scrapers.greenhouse import GreenhouseScraper
from .scrapers.jobright import JobrightScraper
from .scrapers.lever import LeverScraper
from .scrapers.linkedin import LinkedInJobsScraper

logger = structlog.get_logger()


class JobDiscoveryState(TypedDict):
    """State for job discovery workflow."""

    query: str
    location: Optional[str]
    sources: List[str]
    max_results: int
    jobs: List[Dict[str, Any]]
    errors: List[str]
    processed_count: int


class JobDiscoveryAgent:
    """Agent for discovering jobs from multiple sources."""

    def __init__(self):
        self.scrapers = {
            "jobright": JobrightScraper(),
            "linkedin": LinkedInJobsScraper(),
            "greenhouse": GreenhouseScraper(),
            "lever": LeverScraper(),
        }
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        graph = StateGraph(JobDiscoveryState)

        graph.add_node("scrape_sources", self._scrape_sources)
        graph.add_node("deduplicate", self._deduplicate)
        graph.add_node("store", self._store_jobs)

        graph.set_entry_point("scrape_sources")
        graph.add_edge("scrape_sources", "deduplicate")
        graph.add_edge("deduplicate", "store")
        graph.add_edge("store", END)

        return graph.compile()

    async def _scrape_sources(self, state: JobDiscoveryState) -> Dict[str, Any]:
        """Scrape jobs from all configured sources in parallel."""
        tasks = []
        active_sources = []

        for source in state["sources"]:
            if source in self.scrapers:
                scraper = self.scrapers[source]
                tasks.append(
                    scraper.scrape(
                        query=state["query"],
                        location=state.get("location"),
                        max_results=state["max_results"],
                    )
                )
                active_sources.append(source)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_jobs = []
        errors = []

        for source, result in zip(active_sources, results):
            if isinstance(result, Exception):
                error_msg = f"{source}: {str(result)}"
                errors.append(error_msg)
                logger.error("scraper_error", source=source, error=str(result))
            else:
                all_jobs.extend(result)
                logger.info(
                    "scraper_complete", source=source, job_count=len(result)
                )

        return {
            "jobs": all_jobs,
            "errors": state.get("errors", []) + errors,
        }

    async def _deduplicate(self, state: JobDiscoveryState) -> Dict[str, Any]:
        """Remove duplicate jobs based on URL hash."""
        seen_hashes = set()
        unique_jobs = []

        for job in state["jobs"]:
            url_hash = hashlib.sha256(job["url"].encode()).hexdigest()[:64]
            if url_hash not in seen_hashes:
                seen_hashes.add(url_hash)
                job["url_hash"] = url_hash
                unique_jobs.append(job)

        logger.info(
            "deduplication_complete",
            original=len(state["jobs"]),
            unique=len(unique_jobs),
        )

        return {"jobs": unique_jobs}

    async def _store_jobs(self, state: JobDiscoveryState) -> Dict[str, Any]:
        """Store jobs in database."""
        stored_count = 0

        async with get_db_context() as db:
            for job_data in state["jobs"]:
                try:
                    existing = await db.execute(
                        Job.__table__.select().where(
                            Job.url_hash == job_data["url_hash"]
                        )
                    )
                    if existing.first():
                        continue

                    job = Job(
                        source=JobSource(job_data.get("source", "manual")),
                        external_id=job_data.get("external_id"),
                        url=job_data["url"],
                        url_hash=job_data["url_hash"],
                        company=job_data["company"],
                        role=job_data["role"],
                        location=job_data.get("location"),
                        description=job_data.get("description"),
                        skills=job_data.get("skills"),
                        salary_range=job_data.get("salary_range"),
                        posted_date=job_data.get("posted_date"),
                        status=JobStatus.NEW,
                    )
                    db.add(job)
                    stored_count += 1

                except Exception as e:
                    logger.error(
                        "store_job_error",
                        url=job_data.get("url"),
                        error=str(e),
                    )

            await db.commit()

        logger.info("jobs_stored", count=stored_count)
        return {"processed_count": stored_count}

    async def discover(
        self,
        query: str,
        location: Optional[str] = None,
        sources: Optional[List[str]] = None,
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """Run job discovery workflow."""
        if sources is None:
            sources = ["jobright", "greenhouse", "lever"]

        initial_state: JobDiscoveryState = {
            "query": query,
            "location": location,
            "sources": sources,
            "max_results": max_results,
            "jobs": [],
            "errors": [],
            "processed_count": 0,
        }

        logger.info(
            "job_discovery_start",
            query=query,
            location=location,
            sources=sources,
        )

        result = await self.graph.ainvoke(initial_state)

        logger.info(
            "job_discovery_complete",
            jobs_found=len(result["jobs"]),
            jobs_stored=result["processed_count"],
            errors=len(result["errors"]),
        )

        return {
            "jobs_found": len(result["jobs"]),
            "jobs_stored": result["processed_count"],
            "errors": result["errors"],
        }
