"""LinkedIn Execution Agent using Playwright."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from sqlalchemy import select, update

from src.core.config import settings
from src.core.database import get_db_context
from src.core.rate_limiter import random_delay, rate_limiter
from src.models.db_models import (
    HiringManager,
    OutreachLog,
    OutreachQueue,
    OutreachStatus,
)

from .browser_actions import BrowserActions
from .safety import SafetyManager

logger = structlog.get_logger()


class LinkedInExecutorAgent:
    """Agent for executing LinkedIn connection requests."""

    def __init__(self):
        self.safety = SafetyManager()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.actions: Optional[BrowserActions] = None

    async def __aenter__(self):
        await self._setup_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cleanup()

    async def _setup_browser(self) -> None:
        """Set up Playwright browser with persistent context."""
        playwright = await async_playwright().start()

        self.browser = await playwright.chromium.launch(
            headless=settings.browser_headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        storage_state = None
        try:
            import os
            storage_file = f"{settings.browser_data_dir}/linkedin_state.json"
            if os.path.exists(storage_file):
                storage_state = storage_file
        except Exception:
            pass

        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            storage_state=storage_state,
        )

        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        self.page = await self.context.new_page()
        self.actions = BrowserActions(self.page)

        logger.info("browser_setup_complete")

    async def _cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self.context:
                import os
                os.makedirs(settings.browser_data_dir, exist_ok=True)
                await self.context.storage_state(
                    path=f"{settings.browser_data_dir}/linkedin_state.json"
                )
        except Exception as e:
            logger.warning("save_state_error", error=str(e))

        if self.browser:
            await self.browser.close()

        logger.info("browser_cleanup_complete")

    async def _ensure_logged_in(self) -> bool:
        """Check if logged into LinkedIn, prompt for manual login if not."""
        await self.page.goto("https://www.linkedin.com/feed/")
        await asyncio.sleep(3)

        if "login" in self.page.url or "checkpoint" in self.page.url:
            logger.warning("linkedin_not_logged_in")
            return False

        logger.info("linkedin_logged_in")
        return True

    async def send_connection(
        self, outreach: OutreachQueue, hiring_manager: HiringManager
    ) -> Dict[str, Any]:
        """Send a single connection request."""
        if not await self.safety.can_proceed():
            return {
                "success": False,
                "error": "Safety check failed - outside working hours or limit reached",
            }

        if not await rate_limiter.check_limit("connections"):
            return {
                "success": False,
                "error": "Daily connection limit reached",
            }

        try:
            logger.info(
                "connection_start",
                outreach_id=outreach.id,
                profile_url=hiring_manager.linkedin_url,
            )

            await self.page.goto(hiring_manager.linkedin_url)
            await self.actions.human_delay(2, 5)

            await self.actions.natural_scroll()

            connect_clicked = await self._click_connect_button()
            if not connect_clicked:
                return {
                    "success": False,
                    "error": "Could not find Connect button",
                }

            note_added = await self._add_connection_note(outreach.message)
            if not note_added:
                return {
                    "success": False,
                    "error": "Could not add connection note",
                }

            sent = await self._send_connection()
            if not sent:
                return {
                    "success": False,
                    "error": "Could not send connection request",
                }

            await rate_limiter.record_action("connections")

            await self._log_action(
                outreach.id, "send_connection", "success"
            )

            logger.info(
                "connection_sent",
                outreach_id=outreach.id,
                hm_name=hiring_manager.name,
            )

            return {"success": True}

        except Exception as e:
            logger.error(
                "connection_error",
                outreach_id=outreach.id,
                error=str(e),
            )

            await self._log_action(
                outreach.id, "send_connection", "error", str(e)
            )

            return {"success": False, "error": str(e)}

    async def _click_connect_button(self) -> bool:
        """Click the Connect button on profile."""
        try:
            selectors = [
                'button:has-text("Connect")',
                '[aria-label*="Connect"]',
                '.pvs-profile-actions button:has-text("Connect")',
                'button.artdeco-button--primary:has-text("Connect")',
            ]

            for selector in selectors:
                try:
                    button = await self.page.wait_for_selector(
                        selector, timeout=3000
                    )
                    if button:
                        await self.actions.human_click(button)
                        await self.actions.human_delay(0.5, 1.5)
                        return True
                except Exception:
                    continue

            more_button = await self.page.query_selector(
                'button:has-text("More")'
            )
            if more_button:
                await self.actions.human_click(more_button)
                await self.actions.human_delay(0.5, 1)

                connect_option = await self.page.wait_for_selector(
                    '[aria-label*="Connect"]', timeout=3000
                )
                if connect_option:
                    await self.actions.human_click(connect_option)
                    await self.actions.human_delay(0.5, 1.5)
                    return True

            return False

        except Exception as e:
            logger.warning("click_connect_error", error=str(e))
            return False

    async def _add_connection_note(self, message: str) -> bool:
        """Add a note to the connection request."""
        try:
            add_note_button = await self.page.wait_for_selector(
                'button:has-text("Add a note")', timeout=5000
            )
            if add_note_button:
                await self.actions.human_click(add_note_button)
                await self.actions.human_delay(0.5, 1)

            textarea = await self.page.wait_for_selector(
                'textarea[name="message"], textarea#custom-message',
                timeout=5000,
            )

            if textarea:
                await self.actions.human_type(textarea, message)
                await self.actions.human_delay(1, 2)
                return True

            return False

        except Exception as e:
            logger.warning("add_note_error", error=str(e))
            return False

    async def _send_connection(self) -> bool:
        """Click the Send button."""
        try:
            send_button = await self.page.wait_for_selector(
                'button:has-text("Send"), button[aria-label*="Send"]',
                timeout=5000,
            )

            if send_button:
                await self.actions.human_click(send_button)
                await self.actions.human_delay(1, 2)

                success_indicators = [
                    'text="Pending"',
                    'text="Invitation sent"',
                    '[aria-label*="Pending"]',
                ]

                for indicator in success_indicators:
                    try:
                        await self.page.wait_for_selector(
                            indicator, timeout=3000
                        )
                        return True
                    except Exception:
                        continue

                return True

            return False

        except Exception as e:
            logger.warning("send_connection_error", error=str(e))
            return False

    async def _log_action(
        self,
        outreach_id: str,
        action: str,
        result: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Log action to database."""
        async with get_db_context() as db:
            log = OutreachLog(
                outreach_id=outreach_id,
                action=action,
                result=result,
                error_message=error_message,
                metadata={
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            db.add(log)
            await db.commit()

    async def execute_single(self, outreach_id: str) -> Dict[str, Any]:
        """Execute a single approved outreach."""
        async with get_db_context() as db:
            result = await db.execute(
                select(OutreachQueue, HiringManager)
                .join(HiringManager)
                .where(
                    OutreachQueue.id == outreach_id,
                    OutreachQueue.status == OutreachStatus.APPROVED,
                )
            )
            row = result.first()

            if not row:
                return {"success": False, "error": "Outreach not found or not approved"}

            outreach, hiring_manager = row

        async with self:
            if not await self._ensure_logged_in():
                return {"success": False, "error": "Not logged into LinkedIn"}

            result = await self.send_connection(outreach, hiring_manager)

            async with get_db_context() as db:
                new_status = (
                    OutreachStatus.SENT if result["success"]
                    else OutreachStatus.ERROR
                )
                await db.execute(
                    update(OutreachQueue)
                    .where(OutreachQueue.id == outreach_id)
                    .values(
                        status=new_status,
                        sent_at=datetime.utcnow() if result["success"] else None,
                    )
                )
                await db.commit()

            return result

    async def execute_batch(self, limit: int = 5) -> Dict[str, Any]:
        """Execute a batch of approved outreach requests."""
        if not rate_limiter.is_working_hours():
            logger.info("batch_skip_outside_hours")
            return {"executed": 0, "skipped": 0, "errors": []}

        remaining = await rate_limiter.get_remaining("connections")
        if remaining <= 0:
            logger.info("batch_skip_daily_limit")
            return {"executed": 0, "skipped": 0, "errors": ["Daily limit reached"]}

        actual_limit = min(limit, remaining)

        async with get_db_context() as db:
            result = await db.execute(
                select(OutreachQueue, HiringManager)
                .join(HiringManager)
                .where(OutreachQueue.status == OutreachStatus.APPROVED)
                .order_by(OutreachQueue.created_at)
                .limit(actual_limit)
            )
            rows = result.all()

        if not rows:
            logger.info("batch_no_pending")
            return {"executed": 0, "skipped": 0, "errors": []}

        executed = 0
        skipped = 0
        errors = []

        async with self:
            if not await self._ensure_logged_in():
                return {
                    "executed": 0,
                    "skipped": len(rows),
                    "errors": ["Not logged into LinkedIn"],
                }

            for outreach, hiring_manager in rows:
                if not await self.safety.can_proceed():
                    skipped += len(rows) - executed - skipped
                    break

                result = await self.send_connection(outreach, hiring_manager)

                async with get_db_context() as db:
                    new_status = (
                        OutreachStatus.SENT if result["success"]
                        else OutreachStatus.ERROR
                    )
                    await db.execute(
                        update(OutreachQueue)
                        .where(OutreachQueue.id == outreach.id)
                        .values(
                            status=new_status,
                            sent_at=datetime.utcnow() if result["success"] else None,
                        )
                    )
                    await db.commit()

                if result["success"]:
                    executed += 1
                else:
                    errors.append(result.get("error", "Unknown error"))

                await random_delay()

        logger.info(
            "batch_complete",
            executed=executed,
            skipped=skipped,
            errors=len(errors),
        )

        return {
            "executed": executed,
            "skipped": skipped,
            "errors": errors,
        }
