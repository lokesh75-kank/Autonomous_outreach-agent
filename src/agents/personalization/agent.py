"""AI Personalization Engine using OpenAI."""

from typing import Any, Dict, List, Optional, TypedDict

import structlog
from langgraph.graph import END, StateGraph
from openai import AsyncOpenAI
from sqlalchemy import select

from src.core.config import settings
from src.core.database import get_db_context
from src.models.db_models import (
    HiringManager,
    Job,
    OutreachQueue,
    OutreachStatus,
    UserProfile,
)

from .prompts import (
    MESSAGE_GENERATION_PROMPT,
    SYSTEM_PROMPT,
    FOLLOW_UP_PROMPT,
    THANK_YOU_PROMPT,
)

logger = structlog.get_logger()


class PersonalizationState(TypedDict):
    """State for personalization workflow."""

    job_id: str
    hiring_manager_id: str
    job: Optional[Dict[str, Any]]
    hiring_manager: Optional[Dict[str, Any]]
    user_profile: Optional[Dict[str, Any]]
    generated_message: Optional[str]
    outreach_id: Optional[str]
    errors: List[str]


class PersonalizationEngine:
    """Engine for generating personalized outreach messages."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        graph = StateGraph(PersonalizationState)

        graph.add_node("load_context", self._load_context)
        graph.add_node("generate_message", self._generate_message)
        graph.add_node("validate_message", self._validate_message)
        graph.add_node("create_outreach", self._create_outreach)

        graph.set_entry_point("load_context")
        graph.add_edge("load_context", "generate_message")
        graph.add_edge("generate_message", "validate_message")
        graph.add_edge("validate_message", "create_outreach")
        graph.add_edge("create_outreach", END)

        return graph.compile()

    async def _load_context(self, state: PersonalizationState) -> Dict[str, Any]:
        """Load job, hiring manager, and user profile."""
        async with get_db_context() as db:
            job_result = await db.execute(
                select(Job).where(Job.id == state["job_id"])
            )
            job = job_result.scalar_one_or_none()

            hm_result = await db.execute(
                select(HiringManager).where(
                    HiringManager.id == state["hiring_manager_id"]
                )
            )
            hiring_manager = hm_result.scalar_one_or_none()

            user_result = await db.execute(
                select(UserProfile).where(UserProfile.is_active == True).limit(1)
            )
            user_profile = user_result.scalar_one_or_none()

        errors = []
        if not job:
            errors.append(f"Job not found: {state['job_id']}")
        if not hiring_manager:
            errors.append(f"Hiring manager not found: {state['hiring_manager_id']}")

        return {
            "job": {
                "id": job.id,
                "company": job.company,
                "role": job.role,
                "location": job.location,
                "description": job.description,
                "skills": job.skills,
            } if job else None,
            "hiring_manager": {
                "id": hiring_manager.id,
                "name": hiring_manager.name,
                "title": hiring_manager.title,
                "linkedin_url": hiring_manager.linkedin_url,
            } if hiring_manager else None,
            "user_profile": {
                "name": user_profile.name,
                "resume_text": user_profile.resume_text,
                "skills": user_profile.skills,
                "experience_summary": user_profile.experience_summary,
            } if user_profile else {
                "name": "Job Seeker",
                "resume_text": "",
                "skills": [],
                "experience_summary": "",
            },
            "errors": errors,
        }

    async def _generate_message(self, state: PersonalizationState) -> Dict[str, Any]:
        """Generate personalized message using OpenAI."""
        if state.get("errors") or not state.get("job") or not state.get("hiring_manager"):
            return {"generated_message": None}

        job = state["job"]
        hm = state["hiring_manager"]
        user = state["user_profile"]

        hm_first_name = hm["name"].split()[0] if hm["name"] else "there"

        skills_text = ", ".join(job.get("skills", [])[:5]) if job.get("skills") else "Not specified"

        prompt = MESSAGE_GENERATION_PROMPT.format(
            hm_first_name=hm_first_name,
            hm_name=hm["name"],
            hm_title=hm.get("title", ""),
            company=job["company"],
            role=job["role"],
            skills=skills_text,
            job_description=job.get("description", "")[:500] if job.get("description") else "",
            user_name=user.get("name", ""),
            user_experience=user.get("experience_summary", "")[:300] if user.get("experience_summary") else "",
            user_skills=", ".join(user.get("skills", [])[:5]) if user.get("skills") else "",
        )

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=150,
            )

            message = response.choices[0].message.content.strip()
            message = message.strip('"\'')

            logger.info(
                "message_generated",
                company=job["company"],
                hm_name=hm["name"],
                length=len(message),
            )

            return {"generated_message": message}

        except Exception as e:
            logger.error("openai_error", error=str(e))
            return {
                "generated_message": None,
                "errors": state.get("errors", []) + [str(e)],
            }

    async def _validate_message(self, state: PersonalizationState) -> Dict[str, Any]:
        """Validate and clean generated message."""
        message = state.get("generated_message")

        if not message:
            return {}

        if len(message) > 300:
            message = message[:297] + "..."

        banned_phrases = [
            "i hope this message finds you well",
            "i'm reaching out because",
            "i'd love to connect",
            "i came across your profile",
            "i hope this finds you",
        ]

        message_lower = message.lower()
        for phrase in banned_phrases:
            if phrase in message_lower:
                logger.warning("banned_phrase_detected", phrase=phrase)

        return {"generated_message": message}

    async def _create_outreach(self, state: PersonalizationState) -> Dict[str, Any]:
        """Create outreach queue entry."""
        if not state.get("generated_message") or not state.get("job") or not state.get("hiring_manager"):
            return {"outreach_id": None}

        async with get_db_context() as db:
            existing = await db.execute(
                select(OutreachQueue).where(
                    OutreachQueue.job_id == state["job"]["id"],
                    OutreachQueue.hiring_manager_id == state["hiring_manager"]["id"],
                )
            )
            if existing.scalar_one_or_none():
                logger.info("outreach_exists", job_id=state["job"]["id"])
                return {"outreach_id": None}

            outreach = OutreachQueue(
                job_id=state["job"]["id"],
                hiring_manager_id=state["hiring_manager"]["id"],
                message=state["generated_message"],
                status=OutreachStatus.PENDING_APPROVAL,
            )
            db.add(outreach)
            await db.commit()
            await db.refresh(outreach)

            logger.info("outreach_created", outreach_id=outreach.id)
            return {"outreach_id": outreach.id}

    async def generate(
        self, job_id: str, hiring_manager_id: str
    ) -> Dict[str, Any]:
        """Generate personalized message for a job/hiring manager pair."""
        initial_state: PersonalizationState = {
            "job_id": job_id,
            "hiring_manager_id": hiring_manager_id,
            "job": None,
            "hiring_manager": None,
            "user_profile": None,
            "generated_message": None,
            "outreach_id": None,
            "errors": [],
        }

        logger.info(
            "personalization_start",
            job_id=job_id,
            hiring_manager_id=hiring_manager_id,
        )

        result = await self.graph.ainvoke(initial_state)

        return {
            "outreach_id": result.get("outreach_id"),
            "message": result.get("generated_message"),
            "errors": result.get("errors", []),
        }

    async def generate_follow_up(
        self, outreach_id: str, follow_up_type: str = "follow_up_1"
    ) -> Optional[str]:
        """Generate follow-up message for existing outreach."""
        async with get_db_context() as db:
            result = await db.execute(
                select(OutreachQueue, Job, HiringManager)
                .join(Job)
                .join(HiringManager)
                .where(OutreachQueue.id == outreach_id)
            )
            row = result.first()
            if not row:
                return None

            outreach, job, hm = row

        hm_first_name = hm.name.split()[0] if hm.name else "there"

        if follow_up_type == "thank_you":
            prompt = THANK_YOU_PROMPT.format(
                hm_first_name=hm_first_name,
                role=job.role,
                company=job.company,
            )
        else:
            prompt = FOLLOW_UP_PROMPT.format(
                hm_first_name=hm_first_name,
                role=job.role,
                company=job.company,
            )

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=150,
            )

            message = response.choices[0].message.content.strip()
            message = message.strip('"\'')

            if len(message) > 300:
                message = message[:297] + "..."

            return message

        except Exception as e:
            logger.error("follow_up_generation_error", error=str(e))
            return None

    async def generate_for_all_pending(self, limit: int = 20) -> Dict[str, Any]:
        """Generate messages for all jobs with hiring managers but no outreach."""
        async with get_db_context() as db:
            subquery = select(OutreachQueue.hiring_manager_id)
            
            result = await db.execute(
                select(HiringManager)
                .where(~HiringManager.id.in_(subquery))
                .order_by(HiringManager.relevance_score.desc())
                .limit(limit)
            )
            hiring_managers = result.scalars().all()

        generated_count = 0
        errors = []

        for hm in hiring_managers:
            try:
                result = await self.generate(hm.job_id, hm.id)
                if result.get("outreach_id"):
                    generated_count += 1
                if result.get("errors"):
                    errors.extend(result["errors"])
            except Exception as e:
                logger.error(
                    "batch_generation_error",
                    hm_id=hm.id,
                    error=str(e),
                )
                errors.append(str(e))

        return {
            "generated_count": generated_count,
            "errors": errors,
        }
