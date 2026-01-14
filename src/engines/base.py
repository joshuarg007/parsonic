"""Base engine interface for Parsonic scrapers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class ScrapeResult:
    """Result from scraping a single URL."""
    url: str
    success: bool
    data: dict[str, Any]
    error: Optional[str] = None
    status_code: Optional[int] = None
    elapsed_ms: float = 0
    html: Optional[str] = None  # Only saved on error if configured


@dataclass
class RobotsWarning:
    """Warning about robots.txt restrictions."""
    url: str
    disallowed_paths: list[str]
    message: str


class BaseEngine(ABC):
    """Abstract base class for scraping engines."""

    @abstractmethod
    async def scrape(self, url: str, fields: list, **kwargs) -> ScrapeResult:
        """Scrape a single URL and extract fields."""
        pass

    @abstractmethod
    async def scrape_batch(self, urls: list[str], fields: list, **kwargs) -> list[ScrapeResult]:
        """Scrape multiple URLs."""
        pass

    @abstractmethod
    async def check_robots(self, url: str) -> Optional[RobotsWarning]:
        """Check robots.txt for the given URL."""
        pass

    @abstractmethod
    async def close(self):
        """Cleanup resources."""
        pass
