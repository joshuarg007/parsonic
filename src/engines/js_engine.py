"""JavaScript rendering engine using Playwright for dynamic sites."""

import asyncio
import random
import time
import hashlib
from typing import Optional, Any
from urllib.parse import urlparse, urljoin

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from bs4 import BeautifulSoup

from src.engines.base import BaseEngine, ScrapeResult, RobotsWarning
from src.models.project import SelectorField, RateLimitConfig, ProxyConfig, AuthConfig, AuthType


# Common user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


class PlaywrightEngine(BaseEngine):
    """Engine for scraping JavaScript-rendered pages using Playwright."""

    def __init__(
        self,
        rate_limit: Optional[RateLimitConfig] = None,
        proxy: Optional[ProxyConfig] = None,
        auth: Optional[AuthConfig] = None,
        timeout: float = 30.0,
        headers: Optional[dict[str, str]] = None,
        retry_count: int = 3,
        save_html_on_error: bool = True,
        respect_robots: bool = True,
        detect_duplicates: bool = True,
        stealth_mode: bool = True,
        headless: bool = True,
        wait_for: str = "networkidle",  # load, domcontentloaded, networkidle
        wait_timeout: float = 10.0,
        session_storage_path: Optional[str] = None,
    ):
        self.rate_limit = rate_limit or RateLimitConfig()
        self.proxy = proxy or ProxyConfig()
        self.auth = auth or AuthConfig()
        self.timeout = timeout
        self.custom_headers = headers or {}
        self.retry_count = retry_count
        self.save_html_on_error = save_html_on_error
        self.respect_robots = respect_robots
        self.detect_duplicates = detect_duplicates
        self.stealth_mode = stealth_mode
        self.headless = headless
        self.wait_for = wait_for
        self.wait_timeout = wait_timeout
        self.session_storage_path = session_storage_path

        # State
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._robots_cache: dict[str, bool] = {}
        self._seen_hashes: set[str] = set()
        self._consecutive_errors = 0

        # Proxy rotation
        self._proxy_index = 0
        self._failed_proxies: set[str] = set()

        # Concurrency
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def _init_browser(self):
        """Initialize Playwright browser."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()

            # Browser launch options
            launch_options = {
                "headless": self.headless,
            }

            # Add proxy if configured
            proxy = self._get_proxy()
            if proxy:
                launch_options["proxy"] = {"server": proxy}

            self._browser = await self._playwright.chromium.launch(**launch_options)

            # Context options
            context_options = {
                "user_agent": random.choice(USER_AGENTS),
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
                "timezone_id": "America/New_York",
            }

            # Add custom headers
            if self.custom_headers:
                context_options["extra_http_headers"] = self.custom_headers

            # Load session storage if available
            if self.session_storage_path:
                try:
                    context_options["storage_state"] = self.session_storage_path
                except Exception:
                    pass

            self._context = await self._browser.new_context(**context_options)

            # Apply stealth if enabled
            if self.stealth_mode:
                await self._apply_stealth(self._context)

            self._semaphore = asyncio.Semaphore(self.rate_limit.max_concurrent)

    async def _apply_stealth(self, context: BrowserContext):
        """Apply stealth techniques to avoid bot detection."""
        # Add init script to modify navigator properties
        await context.add_init_script("""
            // Override webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Override platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });

            // Override hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });

            // Override device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });

            // Chrome specific
            window.chrome = {
                runtime: {}
            };

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

    def _get_proxy(self) -> Optional[str]:
        """Get next proxy from pool."""
        if not self.proxy.enabled or not self.proxy.proxies:
            return None

        available = [p for p in self.proxy.proxies if p not in self._failed_proxies]
        if not available:
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
            delay = min(
                self.rate_limit.max_delay * (2 ** self._consecutive_errors),
                60.0
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

        # Remove tel: prefix
        if value.lower().startswith('tel:'):
            value = value[4:]

        # Remove javascript: prefix
        if value.lower().startswith('javascript:'):
            return ""

        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()

        # Remove zero-width characters
        value = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', value)

        return value

    async def _extract_field(self, page: Page, field: SelectorField) -> Optional[str]:
        """Extract a single field from the page using Playwright."""
        selectors = [field.selector] + field.fallback_selectors

        for selector in selectors:
            try:
                if field.selector_type == "xpath":
                    element = await page.query_selector(f"xpath={selector}")
                else:
                    element = await page.query_selector(selector)

                if element:
                    if field.attribute:
                        value = await element.get_attribute(field.attribute)
                    else:
                        value = await element.text_content()

                    if value:
                        return self._sanitize_value(value.strip())
            except Exception:
                continue

        return None

    def _compute_hash(self, data: dict[str, Any]) -> str:
        """Compute hash for duplicate detection."""
        content = str(sorted(data.items()))
        return hashlib.md5(content.encode()).hexdigest()

    async def check_robots(self, url: str) -> Optional[RobotsWarning]:
        """Check robots.txt (simplified for JS engine)."""
        # For JS engine, we typically bypass robots.txt as we're mimicking a real browser
        # But we still warn if respect_robots is enabled
        if not self.respect_robots:
            return None

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        if base_url in self._robots_cache:
            if not self._robots_cache[base_url]:
                return RobotsWarning(
                    url=url,
                    disallowed_paths=[parsed.path],
                    message=f"Path may be restricted by robots.txt"
                )
            return None

        # For JS engine, we don't strictly enforce robots.txt but mark as checked
        self._robots_cache[base_url] = True
        return None

    async def scrape(
        self,
        url: str,
        fields: list[SelectorField],
        **kwargs
    ) -> ScrapeResult:
        """Scrape a single URL with JavaScript rendering."""
        await self._init_browser()
        start_time = time.time()

        # Rate limiting
        await self._wait_rate_limit()

        last_error = None
        html = None

        for attempt in range(self.retry_count + 1):
            page = None
            try:
                async with self._semaphore:
                    page = await self._context.new_page()

                    # Set timeout
                    page.set_default_timeout(self.timeout * 1000)

                    # Navigate
                    response = await page.goto(
                        url,
                        wait_until=self.wait_for,
                        timeout=self.timeout * 1000
                    )

                    status_code = response.status if response else None

                    # Additional wait for dynamic content
                    if self.wait_timeout > 0:
                        await page.wait_for_timeout(self.wait_timeout * 1000)

                    # Get HTML for debugging
                    html = await page.content()

                    # Extract fields
                    data = {}
                    for field in fields:
                        value = await self._extract_field(page, field)
                        data[field.name] = value

                    # Duplicate detection
                    if self.detect_duplicates:
                        data_hash = self._compute_hash(data)
                        if data_hash in self._seen_hashes:
                            return ScrapeResult(
                                url=url,
                                success=True,
                                data=data,
                                status_code=status_code,
                                elapsed_ms=(time.time() - start_time) * 1000,
                                error="Duplicate detected (skipped)"
                            )
                        self._seen_hashes.add(data_hash)

                    self._consecutive_errors = 0
                    return ScrapeResult(
                        url=url,
                        success=True,
                        data=data,
                        status_code=status_code,
                        elapsed_ms=(time.time() - start_time) * 1000
                    )

            except Exception as e:
                last_error = str(e)
                self._consecutive_errors += 1

            finally:
                if page:
                    await page.close()

            # Wait before retry
            if attempt < self.retry_count:
                await asyncio.sleep(2 ** attempt)

        return ScrapeResult(
            url=url,
            success=False,
            data={},
            error=last_error,
            elapsed_ms=(time.time() - start_time) * 1000,
            html=html if self.save_html_on_error else None
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

        tasks = [
            scrape_with_progress(url, i)
            for i, url in enumerate(urls)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

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

    async def test_selector(self, url: str, selector: str, selector_type: str = "css") -> dict:
        """Test a single selector against a URL. Used for hybrid validation."""
        await self._init_browser()

        page = None
        try:
            page = await self._context.new_page()
            page.set_default_timeout(self.timeout * 1000)

            await page.goto(url, wait_until=self.wait_for, timeout=self.timeout * 1000)

            if self.wait_timeout > 0:
                await page.wait_for_timeout(self.wait_timeout * 1000)

            # Find elements
            if selector_type == "xpath":
                elements = await page.query_selector_all(f"xpath={selector}")
            else:
                elements = await page.query_selector_all(selector)

            results = []
            for el in elements[:10]:  # Limit to 10 results
                text = await el.text_content()
                results.append({
                    "text": text.strip() if text else "",
                    "tag": await el.evaluate("el => el.tagName.toLowerCase()"),
                })

            return {
                "success": True,
                "count": len(elements),
                "samples": results
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "count": 0,
                "samples": []
            }

        finally:
            if page:
                await page.close()

    async def save_session(self, path: str):
        """Save current session (cookies, localStorage) to file."""
        if self._context:
            await self._context.storage_state(path=path)

    async def perform_login(
        self,
        login_url: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
        username: str,
        password: str,
        success_indicator: Optional[str] = None
    ) -> bool:
        """Perform form-based login."""
        await self._init_browser()

        page = None
        try:
            page = await self._context.new_page()
            page.set_default_timeout(self.timeout * 1000)

            await page.goto(login_url, wait_until="networkidle")

            # Fill credentials
            await page.fill(username_selector, username)
            await page.fill(password_selector, password)

            # Submit
            await page.click(submit_selector)

            # Wait for navigation
            await page.wait_for_load_state("networkidle")

            # Check success
            if success_indicator:
                try:
                    await page.wait_for_selector(success_indicator, timeout=5000)
                    return True
                except Exception:
                    return False

            return True

        except Exception:
            return False

        finally:
            if page:
                await page.close()

    async def close(self):
        """Cleanup Playwright resources."""
        if self._context:
            await self._context.close()
            self._context = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
