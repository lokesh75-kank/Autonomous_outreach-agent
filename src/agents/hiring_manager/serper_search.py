"""Serper API integration for Google Search."""

from typing import Any, Dict, List, Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings

logger = structlog.get_logger()


class SerperSearch:
    """Serper API client for Google Search."""

    def __init__(self):
        self.api_key = settings.serper_api_key
        self.base_url = "https://google.serper.dev"
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def search(
        self,
        query: str,
        num_results: int = 10,
        search_type: str = "search",
    ) -> List[Dict[str, Any]]:
        """Perform a Google search via Serper API."""
        if not self.api_key:
            logger.warning("serper_api_key_missing")
            return []

        try:
            response = await self.client.post(
                f"{self.base_url}/{search_type}",
                json={
                    "q": query,
                    "num": num_results,
                },
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("organic", [])
            logger.info(
                "serper_search_complete",
                query=query[:50],
                result_count=len(results),
            )

            return results

        except httpx.HTTPStatusError as e:
            logger.error(
                "serper_http_error",
                status_code=e.response.status_code,
                query=query[:50],
            )
            raise
        except Exception as e:
            logger.error("serper_error", error=str(e), query=query[:50])
            raise

    async def search_images(
        self, query: str, num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for images."""
        return await self.search(query, num_results, search_type="images")

    async def search_news(
        self, query: str, num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for news articles."""
        return await self.search(query, num_results, search_type="news")

    async def get_company_info(self, company: str) -> Optional[Dict[str, Any]]:
        """Get company information from search."""
        try:
            results = await self.search(f"{company} company", num_results=3)
            if results:
                return {
                    "company": company,
                    "snippet": results[0].get("snippet", ""),
                    "url": results[0].get("link", ""),
                }
        except Exception as e:
            logger.warning("company_info_error", company=company, error=str(e))

        return None
