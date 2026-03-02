"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OpenAI
    openai_api_key: str = ""

    # Serper API
    serper_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/outreach_db"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/outreach_db"

    # LinkedIn
    linkedin_session_cookie: str = ""
    linkedin_csrf_token: str = ""

    # Rate Limiting (Safety)
    max_connections_per_day: int = 20
    min_delay_seconds: int = 45
    max_delay_seconds: int = 120
    timezone: str = "America/Los_Angeles"

    # Optimal Outreach Windows (when recruiters/HMs are most active - PST)
    # Morning Rush: 8 AM - 10 AM (recruiters check messages, review applicants)
    # Afternoon Boost: 2 PM - 4 PM (final check before end of day)
    morning_window_start: int = 8
    morning_window_end: int = 10
    afternoon_window_start: int = 14
    afternoon_window_end: int = 16

    # Fallback to general working hours if optimal windows disabled
    use_optimal_windows: bool = True
    working_hours_start: int = 9
    working_hours_end: int = 18

    # Typing simulation (milliseconds)
    typing_delay_min: int = 50
    typing_delay_max: int = 150

    # Follow-up settings
    followup_day_1: int = 3
    followup_day_2: int = 7
    cold_after_days: int = 14

    # Application
    debug: bool = False
    log_level: str = "INFO"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Dashboard
    streamlit_server_port: int = 8501

    # Browser automation
    browser_headless: bool = False
    browser_data_dir: str = "./browser_data"

    @property
    def is_configured(self) -> bool:
        """Check if required API keys are configured."""
        return bool(self.openai_api_key and self.serper_api_key)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
