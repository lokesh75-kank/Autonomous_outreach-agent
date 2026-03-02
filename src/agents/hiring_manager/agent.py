"""Hiring Manager Discovery Agent using Serper API."""

import re
from typing import Any, Dict, List, Optional, TypedDict

import structlog
from langgraph.graph import END, StateGraph
from sqlalchemy import select

from src.core.config import settings
from src.core.database import get_db_context
from src.models.db_models import HiringManager, Job

from .serper_search import SerperSearch

logger = structlog.get_logger()


class HiringManagerState(TypedDict):
    """State for hiring manager discovery workflow."""

    job_id: str
    job: Optional[Dict[str, Any]]
    search_results: List[Dict[str, Any]]
    hiring_managers: List[Dict[str, Any]]
    errors: List[str]


class HiringManagerAgent:
    """Agent for discovering hiring managers for job listings."""

    def __init__(self):
        self.search = SerperSearch()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        graph = StateGraph(HiringManagerState)

        graph.add_node("load_job", self._load_job)
        graph.add_node("search_contacts", self._search_contacts)
        graph.add_node("parse_profiles", self._parse_profiles)
        graph.add_node("score_relevance", self._score_relevance)
        graph.add_node("store", self._store_hiring_managers)

        graph.set_entry_point("load_job")
        graph.add_edge("load_job", "search_contacts")
        graph.add_edge("search_contacts", "parse_profiles")
        graph.add_edge("parse_profiles", "score_relevance")
        graph.add_edge("score_relevance", "store")
        graph.add_edge("store", END)

        return graph.compile()

    async def _load_job(self, state: HiringManagerState) -> Dict[str, Any]:
        """Load job details from database."""
        async with get_db_context() as db:
            result = await db.execute(
                select(Job).where(Job.id == state["job_id"])
            )
            job = result.scalar_one_or_none()

            if not job:
                return {
                    "job": None,
                    "errors": state.get("errors", []) + [f"Job not found: {state['job_id']}"],
                }

            return {
                "job": {
                    "id": job.id,
                    "company": job.company,
                    "role": job.role,
                    "location": job.location,
                    "description": job.description,
                }
            }

    async def _search_contacts(self, state: HiringManagerState) -> Dict[str, Any]:
        """Search for hiring managers using Serper API."""
        job = state.get("job")
        if not job:
            return {"search_results": [], "errors": state.get("errors", [])}

        company = job["company"]
        role = job["role"]

        department = self._extract_department(role)

        queries = [
            f'site:linkedin.com/in "{company}" "{role}" "hiring manager"',
            f'site:linkedin.com/in "{company}" "{department}" manager',
            f'site:linkedin.com/in "{company}" recruiter "{department}"',
            f'site:linkedin.com/in "{company}" "head of" "{department}"',
            f'site:linkedin.com/in "{company}" "talent acquisition"',
        ]

        all_results = []
        for query in queries[:3]:
            try:
                results = await self.search.search(query, num_results=5)
                all_results.extend(results)
            except Exception as e:
                logger.warning("search_error", query=query, error=str(e))

        logger.info("search_complete", result_count=len(all_results))
        return {"search_results": all_results}

    async def _parse_profiles(self, state: HiringManagerState) -> Dict[str, Any]:
        """Parse LinkedIn profiles from search results."""
        hiring_managers = []
        seen_urls = set()

        for result in state.get("search_results", []):
            url = result.get("link", "")

            if not self._is_linkedin_profile(url):
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            profile = self._parse_linkedin_result(result)
            if profile:
                hiring_managers.append(profile)

        logger.info("profiles_parsed", count=len(hiring_managers))
        return {"hiring_managers": hiring_managers}

    async def _score_relevance(self, state: HiringManagerState) -> Dict[str, Any]:
        """Score hiring managers by relevance."""
        job = state.get("job", {})
        role = job.get("role", "").lower()
        department = self._extract_department(role)

        scored = []
        for hm in state.get("hiring_managers", []):
            title = hm.get("title", "").lower()
            score = self._calculate_relevance_score(title, role, department)
            hm["relevance_score"] = score
            scored.append(hm)

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)

        return {"hiring_managers": scored[:10]}

    async def _store_hiring_managers(self, state: HiringManagerState) -> Dict[str, Any]:
        """Store hiring managers in database."""
        job = state.get("job")
        if not job:
            return {}

        stored_count = 0

        async with get_db_context() as db:
            for hm_data in state.get("hiring_managers", []):
                try:
                    existing = await db.execute(
                        select(HiringManager).where(
                            HiringManager.job_id == job["id"],
                            HiringManager.linkedin_url == hm_data["linkedin_url"],
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    hm = HiringManager(
                        job_id=job["id"],
                        name=hm_data["name"],
                        title=hm_data.get("title"),
                        linkedin_url=hm_data["linkedin_url"],
                        company=hm_data.get("company") or job["company"],
                        relevance_score=hm_data.get("relevance_score", 50),
                        status="new",
                    )
                    db.add(hm)
                    stored_count += 1

                except Exception as e:
                    logger.error(
                        "store_hm_error",
                        name=hm_data.get("name"),
                        error=str(e),
                    )

            await db.commit()

        logger.info("hiring_managers_stored", count=stored_count)
        return {}

    def _extract_department(self, role: str) -> str:
        """Extract department from role title."""
        role_lower = role.lower()

        department_keywords = {
            "engineering": ["engineer", "developer", "software", "backend", "frontend", "fullstack"],
            "data": ["data", "analytics", "ml", "machine learning", "ai", "scientist"],
            "product": ["product", "pm", "program"],
            "design": ["design", "ux", "ui", "creative"],
            "marketing": ["marketing", "growth", "content"],
            "sales": ["sales", "account", "business development"],
            "operations": ["operations", "ops", "logistics"],
            "hr": ["hr", "human resources", "people", "recruiting"],
            "finance": ["finance", "accounting", "financial"],
        }

        for dept, keywords in department_keywords.items():
            for keyword in keywords:
                if keyword in role_lower:
                    return dept

        return "engineering"

    def _is_linkedin_profile(self, url: str) -> bool:
        """Check if URL is a LinkedIn profile."""
        return bool(re.match(r"https?://(www\.)?linkedin\.com/in/", url))

    def _parse_linkedin_result(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse LinkedIn profile from search result."""
        url = result.get("link", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")

        title_parts = title.split(" - ")
        name = title_parts[0].strip() if title_parts else ""

        name = re.sub(r"\s*\|.*$", "", name)
        name = re.sub(r"\s*LinkedIn$", "", name, flags=re.IGNORECASE)

        if not name or len(name) < 2:
            return None

        professional_title = ""
        if len(title_parts) > 1:
            professional_title = title_parts[1].strip()

        if not professional_title and snippet:
            professional_title = snippet[:100]

        company = ""
        if len(title_parts) > 2:
            company = title_parts[2].strip()
            company = re.sub(r"\s*\|.*$", "", company)

        return {
            "name": name,
            "title": professional_title,
            "linkedin_url": url,
            "company": company,
        }

    def _calculate_relevance_score(
        self, title: str, role: str, department: str
    ) -> int:
        """Calculate relevance score for a hiring manager."""
        score = 50

        high_relevance = [
            "hiring manager",
            f"{department} manager",
            f"head of {department}",
            f"director of {department}",
            f"vp of {department}",
            f"{department} lead",
        ]

        medium_relevance = [
            "manager",
            "director",
            "head of",
            "lead",
            "senior",
        ]

        recruiter_terms = [
            "technical recruiter",
            "talent acquisition",
            "recruiter",
            "recruiting",
            "hr",
            "human resources",
        ]

        for term in high_relevance:
            if term in title:
                score += 40
                break

        for term in medium_relevance:
            if term in title:
                score += 20
                break

        for term in recruiter_terms:
            if term in title:
                score += 15
                break

        if department in title:
            score += 10

        return min(100, score)

    async def discover(self, job_id: str) -> Dict[str, Any]:
        """Run hiring manager discovery for a job."""
        initial_state: HiringManagerState = {
            "job_id": job_id,
            "job": None,
            "search_results": [],
            "hiring_managers": [],
            "errors": [],
        }

        logger.info("hiring_manager_discovery_start", job_id=job_id)

        result = await self.graph.ainvoke(initial_state)

        return {
            "job_id": job_id,
            "hiring_managers_found": len(result.get("hiring_managers", [])),
            "errors": result.get("errors", []),
        }

    async def discover_for_all_new_jobs(self, limit: int = 10) -> Dict[str, Any]:
        """Discover hiring managers for all new jobs."""
        async with get_db_context() as db:
            result = await db.execute(
                select(Job)
                .where(Job.status == "new")
                .order_by(Job.discovered_at.desc())
                .limit(limit)
            )
            jobs = result.scalars().all()

        total_found = 0
        processed = 0

        for job in jobs:
            try:
                result = await self.discover(job.id)
                total_found += result.get("hiring_managers_found", 0)
                processed += 1
            except Exception as e:
                logger.error("batch_discovery_error", job_id=job.id, error=str(e))

        return {
            "jobs_processed": processed,
            "total_hiring_managers_found": total_found,
        }
