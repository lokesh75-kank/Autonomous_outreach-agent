"""Human-like browser actions for LinkedIn automation."""

import asyncio
import random
from typing import Optional

import structlog
from playwright.async_api import ElementHandle, Page

from src.core.config import settings

logger = structlog.get_logger()


class BrowserActions:
    """Human-like browser interaction methods."""

    def __init__(self, page: Page):
        self.page = page

    async def human_delay(
        self,
        min_seconds: float = 0.5,
        max_seconds: float = 2.0,
    ) -> None:
        """Wait for a random human-like duration."""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def human_type(
        self,
        element: ElementHandle,
        text: str,
        mistakes: bool = True,
    ) -> None:
        """Type text with human-like delays and occasional mistakes."""
        for i, char in enumerate(text):
            delay = random.randint(
                settings.typing_delay_min,
                settings.typing_delay_max,
            )

            if mistakes and random.random() < 0.02 and char.isalpha():
                typo = random.choice("qwertyuiopasdfghjklzxcvbnm")
                await element.type(typo, delay=delay)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await element.press("Backspace")
                await asyncio.sleep(random.uniform(0.05, 0.15))

            await element.type(char, delay=delay)

            if char in ".!?,;:":
                await asyncio.sleep(random.uniform(0.1, 0.3))

            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.2, 0.5))

    async def human_click(
        self,
        element: ElementHandle,
        move_mouse: bool = True,
    ) -> None:
        """Click an element with human-like behavior."""
        if move_mouse:
            await self._move_to_element(element)

        await asyncio.sleep(random.uniform(0.05, 0.15))
        await element.click()

    async def _move_to_element(self, element: ElementHandle) -> None:
        """Move mouse to element with natural movement."""
        try:
            box = await element.bounding_box()
            if not box:
                return

            target_x = box["x"] + box["width"] / 2 + random.uniform(-5, 5)
            target_y = box["y"] + box["height"] / 2 + random.uniform(-5, 5)

            current = await self.page.evaluate(
                "() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })"
            )

            steps = random.randint(8, 15)
            for i in range(steps):
                progress = (i + 1) / steps
                progress = self._ease_out_cubic(progress)

                x = current.get("x", 0) + (target_x - current.get("x", 0)) * progress
                y = current.get("y", 0) + (target_y - current.get("y", 0)) * progress

                x += random.uniform(-2, 2)
                y += random.uniform(-2, 2)

                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.01, 0.03))

        except Exception as e:
            logger.debug("mouse_move_error", error=str(e))

    def _ease_out_cubic(self, x: float) -> float:
        """Easing function for natural movement."""
        return 1 - pow(1 - x, 3)

    async def natural_scroll(
        self,
        direction: str = "down",
        amount: Optional[int] = None,
    ) -> None:
        """Scroll the page naturally."""
        if amount is None:
            amount = random.randint(200, 400)

        if direction == "up":
            amount = -amount

        scroll_steps = random.randint(3, 6)
        step_amount = amount // scroll_steps

        for _ in range(scroll_steps):
            step = step_amount + random.randint(-20, 20)
            await self.page.evaluate(f"""
                window.scrollBy({{
                    top: {step},
                    behavior: 'smooth'
                }})
            """)
            await asyncio.sleep(random.uniform(0.1, 0.3))

        await asyncio.sleep(random.uniform(0.3, 0.7))

    async def scroll_to_element(self, element: ElementHandle) -> None:
        """Scroll element into view naturally."""
        await element.scroll_into_view_if_needed()
        await asyncio.sleep(random.uniform(0.3, 0.6))

    async def hover(self, element: ElementHandle) -> None:
        """Hover over an element."""
        await self._move_to_element(element)
        await asyncio.sleep(random.uniform(0.1, 0.3))

    async def random_mouse_movement(self) -> None:
        """Make random mouse movements to appear human."""
        viewport = await self.page.evaluate(
            "() => ({ width: window.innerWidth, height: window.innerHeight })"
        )

        x = random.randint(100, viewport.get("width", 800) - 100)
        y = random.randint(100, viewport.get("height", 600) - 100)

        await self.page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.05, 0.15))

    async def wait_for_network_idle(self, timeout: int = 5000) -> None:
        """Wait for network to be idle."""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            pass
