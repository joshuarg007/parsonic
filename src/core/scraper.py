"""Scraper orchestrator that connects UI to engines."""

import asyncio
from typing import Optional, Union
from PyQt6.QtCore import QObject, pyqtSignal

from src.models.project import ScraperProject, SiteType
from src.engines.base import BaseEngine, ScrapeResult, RobotsWarning
from src.engines.static_engine import StaticEngine
from src.engines.js_engine import PlaywrightEngine


class ScraperOrchestrator(QObject):
    """Orchestrates scraping operations between UI and engines."""

    # Signals
    progress = pyqtSignal(int, int, object)  # current, total, result
    completed = pyqtSignal(list)  # list of results
    error = pyqtSignal(str)  # error message
    log = pyqtSignal(str, str)  # level, message
    robots_warning = pyqtSignal(object)  # RobotsWarning
    paused = pyqtSignal(str, object)  # reason, context for user decision
    validation_complete = pyqtSignal(dict)  # validation result

    def __init__(self, project: ScraperProject):
        super().__init__()
        self.project = project
        self._static_engine: Optional[StaticEngine] = None
        self._js_engine: Optional[PlaywrightEngine] = None
        self._running = False
        self._paused = False
        self._stop_requested = False

    def _get_engine_type(self) -> str:
        """Determine which engine to use based on site type."""
        site_type = self.project.target.site_type

        if site_type == SiteType.STATIC:
            return "static"
        elif site_type == SiteType.JAVASCRIPT:
            return "js"
        elif site_type == SiteType.API:
            return "static"  # API uses static engine with JSON parsing
        else:  # AUTO
            # Default to static, could add detection logic here
            return "static"

    async def _get_engine(self) -> Union[StaticEngine, PlaywrightEngine]:
        """Get or create the appropriate engine."""
        engine_type = self._get_engine_type()

        if engine_type == "js":
            if self._js_engine is None:
                self._js_engine = PlaywrightEngine(
                    rate_limit=self.project.rate_limit,
                    proxy=self.project.proxy,
                    auth=self.project.auth,
                    timeout=self.project.timeout,
                    headers=self.project.target.headers,
                    retry_count=self.project.retry_count,
                    save_html_on_error=True,
                    respect_robots=self.project.respect_robots_txt,
                    detect_duplicates=self.project.detect_duplicates,
                    stealth_mode=True,
                    headless=True,
                )
            return self._js_engine
        else:
            if self._static_engine is None:
                self._static_engine = StaticEngine(
                    rate_limit=self.project.rate_limit,
                    proxy=self.project.proxy,
                    timeout=self.project.timeout,
                    headers=self.project.target.headers,
                    retry_count=self.project.retry_count,
                    save_html_on_error=True,
                    respect_robots=self.project.respect_robots_txt,
                    detect_duplicates=self.project.detect_duplicates,
                )
            return self._static_engine

    async def _get_js_engine(self) -> PlaywrightEngine:
        """Get JS engine specifically (for validation)."""
        if self._js_engine is None:
            self._js_engine = PlaywrightEngine(
                rate_limit=self.project.rate_limit,
                proxy=self.project.proxy,
                auth=self.project.auth,
                timeout=self.project.timeout,
                headers=self.project.target.headers,
                retry_count=self.project.retry_count,
                save_html_on_error=True,
                respect_robots=self.project.respect_robots_txt,
                detect_duplicates=self.project.detect_duplicates,
                stealth_mode=True,
                headless=True,
            )
        return self._js_engine

    async def test_single_url(self, url: str = None) -> ScrapeResult:
        """Test scraping on a single URL."""
        if not url:
            if self.project.target.urls:
                url = self.project.target.urls[0]
            else:
                return ScrapeResult(
                    url="",
                    success=False,
                    data={},
                    error="No URL provided"
                )

        self.log.emit("info", f"Testing URL: {url}")
        self.log.emit("info", f"Engine: {self._get_engine_type()}")

        engine = await self._get_engine()

        # Check robots.txt first
        warning = await engine.check_robots(url)
        if warning:
            self.robots_warning.emit(warning)
            self.log.emit("warning", warning.message)

        # Scrape
        result = await engine.scrape(url, self.project.fields)

        if result.success:
            self.log.emit("info", f"Test successful: extracted {len(result.data)} fields")
        else:
            self.log.emit("error", f"Test failed: {result.error}")

        return result

    async def validate_selector(self, url: str, selector: str, selector_type: str = "css") -> dict:
        """Validate a selector using Playwright (hybrid validation)."""
        self.log.emit("info", f"Validating selector with Playwright: {selector}")

        engine = await self._get_js_engine()
        result = await engine.test_selector(url, selector, selector_type)

        if result["success"]:
            self.log.emit("info", f"Selector found {result['count']} elements")
        else:
            self.log.emit("warning", f"Selector validation failed: {result.get('error', 'No elements found')}")

        self.validation_complete.emit(result)
        return result

    async def run(self) -> list[ScrapeResult]:
        """Run the full scraper with optional crawling."""
        if not self.project.target.urls:
            self.error.emit("No URLs to scrape")
            return []

        if not self.project.fields:
            self.error.emit("No fields defined")
            return []

        self._running = True
        self._stop_requested = False
        results = []

        engine_type = self._get_engine_type()
        crawl_enabled = self.project.link_follow.enabled
        link_selectors = self.project.link_follow.link_selectors  # Now a list
        max_pages = self.project.link_follow.max_depth if crawl_enabled else len(self.project.target.urls)
        same_domain = self.project.link_follow.same_domain_only

        # Debug crawl settings
        self.log.emit("info", f"Crawl enabled: {crawl_enabled}, selectors: {link_selectors}, max: {max_pages}")

        # URL queue for crawling
        url_queue = list(self.project.target.urls)
        seen_urls = set(url_queue)
        pages_scraped = 0

        if crawl_enabled and link_selectors:
            self.log.emit("info", f"Starting crawl (max {max_pages} pages, engine: {engine_type})")
            self.log.emit("info", f"Following links matching: {', '.join(link_selectors)}")
        else:
            self.log.emit("info", f"Starting scrape of {len(url_queue)} URLs (engine: {engine_type})")
            if crawl_enabled and not link_selectors:
                self.log.emit("warning", "Crawl enabled but no link selectors specified!")

        engine = await self._get_engine()

        while url_queue and pages_scraped < max_pages:
            if self._stop_requested:
                self.log.emit("warning", "Scrape stopped by user")
                break

            url = url_queue.pop(0)
            pages_scraped += 1

            # Log current page being crawled
            self.log.emit("info", f"Crawling: {url}")

            # Check robots
            warning = await engine.check_robots(url)
            if warning:
                self.robots_warning.emit(warning)
                self.log.emit("warning", f"robots.txt warning for {url}")

            # Scrape
            result = await engine.scrape(url, self.project.fields)

            # Handle errors that need user decision
            if not result.success and self._should_pause_on_error(result):
                self._paused = True
                self.paused.emit(result.error, result)

                # Wait for user decision
                while self._paused and not self._stop_requested:
                    await asyncio.sleep(0.1)

                if self._stop_requested:
                    break

            results.append(result)

            # If crawling enabled, extract and queue new links
            if crawl_enabled and link_selectors:
                if result.html:
                    all_new_links = []
                    for selector in link_selectors:
                        links = self._extract_links(result.html, url, selector, same_domain)
                        all_new_links.extend(links)

                    # Deduplicate within this page's links
                    all_new_links = list(dict.fromkeys(all_new_links))

                    added = 0
                    for link in all_new_links:
                        if link not in seen_urls:
                            seen_urls.add(link)
                            url_queue.append(link)
                            added += 1

                    if all_new_links:
                        self.log.emit("info", f"Found {len(all_new_links)} links, added {added} new, {len(url_queue)} in queue")
                    else:
                        self.log.emit("warning", f"No links found matching selectors")
                else:
                    self.log.emit("warning", "No HTML available for link extraction")

            # Progress - show queue size if crawling
            if crawl_enabled:
                self.progress.emit(pages_scraped, max_pages, result)
                status = "OK" if result.success else result.error
                # Show what data was extracted
                if result.success and result.data:
                    fields_found = [k for k, v in result.data.items() if v]
                    if fields_found:
                        self.log.emit("info", f"[{pages_scraped}/{max_pages}] {url[:50]}... - {status} (found: {', '.join(fields_found)})")
                    else:
                        self.log.emit("warning", f"[{pages_scraped}/{max_pages}] {url[:50]}... - {status} (no data extracted)")
                else:
                    self.log.emit("info", f"[{pages_scraped}/{max_pages}] {url[:50]}... - {status}")
            else:
                self.progress.emit(pages_scraped, len(self.project.target.urls), result)
                if result.success:
                    self.log.emit("info", f"[{pages_scraped}/{len(self.project.target.urls)}] {url} - OK")
                else:
                    self.log.emit("error", f"[{pages_scraped}/{len(self.project.target.urls)}] {url} - {result.error}")

        self._running = False
        self.completed.emit(results)
        self.log.emit("info", f"Scrape completed: {sum(1 for r in results if r.success)}/{len(results)} successful")

        return results

    def _extract_links(self, html: str, base_url: str, selector: str, same_domain: bool) -> list[str]:
        """Extract links from HTML matching the selector."""
        from urllib.parse import urljoin, urlparse
        from bs4 import BeautifulSoup

        links = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            base_domain = urlparse(base_url).netloc

            for el in soup.select(selector):
                href = el.get('href')
                if href:
                    # Make absolute URL
                    full_url = urljoin(base_url, href)

                    # Skip non-http links
                    if not full_url.startswith(('http://', 'https://')):
                        continue

                    # Check same domain
                    if same_domain:
                        link_domain = urlparse(full_url).netloc
                        if link_domain != base_domain:
                            continue

                    # Skip anchors and common non-page URLs
                    if '#' in full_url or full_url.endswith(('.pdf', '.jpg', '.png', '.gif', '.css', '.js')):
                        continue

                    links.append(full_url)
        except Exception as e:
            self.log.emit("warning", f"Error extracting links: {e}")

        return links

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
        """Perform form-based login using Playwright."""
        self.log.emit("info", f"Attempting login at {login_url}")

        engine = await self._get_js_engine()
        success = await engine.perform_login(
            login_url=login_url,
            username_selector=username_selector,
            password_selector=password_selector,
            submit_selector=submit_selector,
            username=username,
            password=password,
            success_indicator=success_indicator
        )

        if success:
            self.log.emit("info", "Login successful")
        else:
            self.log.emit("error", "Login failed")

        return success

    async def save_session(self, path: str):
        """Save current browser session to file."""
        if self._js_engine:
            await self._js_engine.save_session(path)
            self.log.emit("info", f"Session saved to {path}")

    def _should_pause_on_error(self, result: ScrapeResult) -> bool:
        """Determine if we should pause for user decision on this error."""
        # Pause on non-recoverable errors after retries
        return result.error and "HTTP 4" in str(result.error)

    def resume(self):
        """Resume after pause."""
        self._paused = False

    def skip_current(self):
        """Skip current URL and continue."""
        self._paused = False

    def stop(self):
        """Stop the scraper."""
        self._stop_requested = True
        self._paused = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    async def close(self):
        """Cleanup resources."""
        if self._static_engine:
            await self._static_engine.close()
            self._static_engine = None

        if self._js_engine:
            await self._js_engine.close()
            self._js_engine = None
