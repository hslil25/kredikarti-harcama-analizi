"""Runtime configuration loaded from environment / .env."""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache
def get_settings() -> "Settings":
    return Settings()


class Settings:
    def __init__(self) -> None:
        self.evds_api_key: str = os.getenv("EVDS_API_KEY", "")
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data.db")

    @property
    def has_key(self) -> bool:
        return bool(self.evds_api_key)
