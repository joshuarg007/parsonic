"""Static HTML scraping engine using httpx and BeautifulSoup."""

import asyncio
import random
import time
import hashlib
from typing import Optional, Any
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
import lxml  # noqa: F401 - Used by BeautifulSoup

from src.engines.base import BaseEngine, ScrapeResult, RobotsWarning
from src.models.project import SelectorField, RateLimitConfig, ProxyConfig


# Common user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class StaticEngine(BaseEngine):
    """Engine for scraping static HTML pages."""

    def __init__(
        self,
        rate_limit: Optional[RateLimitConfig] = None,
        proxy: Optional[ProxyConfig] = None,
        timeout: float = 30.0,
        headers: Optional[dict[str, str]] = None,
        retry_count: int = 3,
        save_html_on_error: bool = True,
        respect_robots: bool = True,
        detect_duplicates: bool = True,
    ):
        self.rate_limit = rate_limit or RateLimitConfig()
        self.proxy = proxy or ProxyConfig()
        self.timeout = timeout
        self.custom_headers = headers or {}
        self.retry_count = retry_count
        self.save_html_on_error = save_html_on_error
        self.respect_robots = respect_robots
        self.detect_duplicates = detect_duplicates

        # State
        self._client: Optional[httpx.AsyncClient] = None
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._seen_hashes: set[str] = set()
        self._request_times: list[float] = []
        self._consecutive_errors = 0

        # Proxy rotation state
        self._proxy_index = 0
        self._failed_proxies: set[str] = set()

        # Semaphore for concurrency control
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
            )
            self._semaphore = asyncio.Semaphore(self.rate_limit.max_concurrent)
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Get request headers with random user agent."""
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        headers.update(self.custom_headers)
        return headers

    def _get_proxy(self) -> Optional[str]:
        """Get next proxy from pool."""
        if not self.proxy.enabled or not self.proxy.proxies:
            return None

        available = [p for p in self.proxy.proxies if p not in self._failed_proxies]
        if not available:
            # Reset failed proxies if all failed
            self._failed_proxies.clear()
            available = self.proxy.proxies

        if self.proxy.rotate:
            self._proxy_index = (self._proxy_index + 1) % len(available)
            return available[self._proxy_index]
        else:
            return available[0]

    async def _wait_rate_limit(self):
        """Apply rate limiting delay."""
        if self.rate_limit.adaptive and self._consecutive_errors > 0:
            # Back off on errors
            delay = min(
                self.rate_limit.max_delay * (2 ** self._consecutive_errors),
                60.0  # Max 60 second delay
            )
        else:
            delay = random.uniform(self.rate_limit.min_delay, self.rate_limit.max_delay)

        if delay > 0:
            await asyncio.sleep(delay)

    def _sanitize_value(self, value: str) -> str:
        """Clean up extracted values (remove mailto:, tel:, etc.)."""
        import re

        if not value:
            return value

        # Remove mailto: prefix
        if value.lower().startswith('mailto:'):
            value = value[7:]

        # Remove tel: prefix and clean phone numbers
        if value.lower().startswith('tel:'):
            value = value[4:]

        # Remove javascript: prefix (sometimes on href)
        if value.lower().startswith('javascript:'):
            return ""

        # Remove common URL prefixes if it's clearly an email/phone
        # (but keep http/https for actual URLs)

        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()

        # Remove zero-width characters
        value = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', value)

        return value

    def _extract_field(self, soup: BeautifulSoup, field: SelectorField) -> Optional[str]:
        """Extract a single field from the page."""
        selectors = [field.selector] + field.fallback_selectors

        for selector in selectors:
            try:
                if field.selector_type == "xpath":
                    # Convert XPath to CSS for BeautifulSoup (limited support)
                    # For full XPath support, would need lxml directly
                    continue  # Skip XPath for now, use CSS
                else:
                    element = soup.select_one(selector)

                if element:
                    if field.attribute:
                        value = element.get(field.attribute)
                    else:
                        value = element.get_text(strip=True)

                    if value:
                        return self._sanitize_value(str(value))
            except Exception:
                continue

        return None

    def _compute_hash(self, data: dict[str, Any]) -> str:
        """Compute hash of extracted data for duplicate detection."""
        content = str(sorted(data.items()))
        return hashlib.md5(content.encode()).hexdigest()

    async def check_robots(self, url: str) -> Optional[RobotsWarning]:
        """Check robots.txt for the given URL."""
        if not self.respect_robots:
            return None

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = urljoin(base_url, "/robots.txt")

        if base_url not in self._robots_cache:
            try:
                client = await self._get_client()
                response = await client.get(robots_url, headers=self._get_headers())

                rp = RobotFileParser()
                rp.parse(response.text.splitlines())
                self._robots_cache[base_url] = rp
            except Exception:
                # If we can't fetch robots.txt, assume everything is allowed
                return None

        rp = self._robots_cache.get(base_url)
        if rp and not rp.can_fetch("*", url):
            return RobotsWarning(
                url=url,
                disallowed_paths=[parsed.path],
                message=f"URL path '{parsed.path}' is disallowed by robots.txt"
            )

        return None

    async def scrape(
        self,
        url: str,
        fields: list[SelectorField],
        **kwargs
    ) -> ScrapeResult:
        """Scrape a single URL."""
        client = await self._get_client()
        start_time = time.time()

        # Check robots.txt
        robots_warning = await self.check_robots(url)
        if robots_warning:
            return ScrapeResult(
                url=url,
                success=False,
                data={},
                error=f"Blocked by robots.txt: {robots_warning.message}",
                elapsed_ms=(time.time() - start_time) * 1000
            )

        # Apply rate limiting
        await self._wait_rate_limit()

        # Retry loop
        last_error = None
        html = None

        for attempt in range(self.retry_count + 1):
            try:
                proxy = self._get_proxy()
                transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None

                async with self._semaphore:
                    if transport:
                        async with httpx.AsyncClient(transport=transport, timeout=self.timeout) as proxy_client:
                            response = await proxy_client.get(url, headers=self._get_headers())
                    else:
                        response = await client.get(url, headers=self._get_headers())

                response.raise_for_status()
                html = response.text
                status_code = response.status_code

                # Parse HTML
                soup = BeautifulSoup(html, 'lxml')

                # Extract fields
                data = {}
                for field in fields:
                    value = self._extract_field(soup, field)
                    data[field.name] = value

                # Check for duplicates
                if self.detect_duplicates:
                    data_hash = self._compute_hash(data)
                    if data_hash in self._seen_hashes:
                        return ScrapeResult(
                            url=url,
                            success=True,
                            data=data,
                            status_code=status_code,
                            elapsed_ms=(time.time() - start_time) * 1000,
                            error="Duplicate detected (skipped)",
                            html=html  # Include for crawling
                        )
                    self._seen_hashes.add(data_hash)

                self._consecutive_errors = 0
                return ScrapeResult(
                    url=url,
                    success=True,
                    data=data,
                    status_code=status_code,
                    elapsed_ms=(time.time() - start_time) * 1000,
                    html=html  # Include for crawling
                )

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
                self._consecutive_errors += 1

                if proxy:
                    self._failed_proxies.add(proxy)

            except httpx.RequestError as e:
                last_error = f"Request failed: {str(e)}"
                self._consecutive_errors += 1

                if proxy:
                    self._failed_proxies.add(proxy)

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                self._consecutive_errors += 1

            # Wait before retry
            if attempt < self.retry_count:
                await asyncio.sleep(2 ** attempt)

        # All retries failed
        return ScrapeResult(
            url=url,
            success=False,
            data={},
            error=last_error,
            elapsed_ms=(time.time() - start_time) * 1000,
            html=html  # Always include for crawling
        )

    async def scrape_batch(
        self,
        urls: list[str],
        fields: list[SelectorField],
        progress_callback=None,
        **kwargs
    ) -> list[ScrapeResult]:
        """Scrape multiple URLs with concurrency control."""
        results = []

        async def scrape_with_progress(url: str, index: int):
            result = await self.scrape(url, fields, **kwargs)
            if progress_callback:
                progress_callback(index + 1, len(urls), result)
            return result

        # Create tasks
        tasks = [
            scrape_with_progress(url, i)
            for i, url in enumerate(urls)
        ]

        # Run with concurrency limit (already handled by semaphore)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ScrapeResult(
                    url=urls[i],
                    success=False,
                    data={},
                    error=str(result)
                ))
            else:
                final_results.append(result)

        return final_results

    async def close(self):
        """Cleanup HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
