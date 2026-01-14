"""Proxy manager with health checks and rotation for Parsonic."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class ProxyStatus:
    """Status information for a single proxy."""
    url: str
    is_healthy: bool = True
    last_check: float = 0
    response_time_ms: float = 0
    fail_count: int = 0
    success_count: int = 0
    last_error: Optional[str] = None


@dataclass
class ProxyPool:
    """Pool of proxies with health tracking."""
    proxies: dict[str, ProxyStatus] = field(default_factory=dict)
    current_index: int = 0
    health_check_url: str = "https://httpbin.org/ip"
    health_check_interval: float = 300.0  # 5 minutes
    max_fail_count: int = 3
    timeout: float = 10.0


class ProxyManager:
    """Manages proxy rotation with health checks."""

    def __init__(
        self,
        proxies: list[str],
        health_check_url: str = "https://httpbin.org/ip",
        health_check_interval: float = 300.0,
        max_fail_count: int = 3,
        timeout: float = 10.0
    ):
        self.pool = ProxyPool(
            health_check_url=health_check_url,
            health_check_interval=health_check_interval,
            max_fail_count=max_fail_count,
            timeout=timeout
        )

        # Initialize proxy statuses
        for proxy in proxies:
            self.pool.proxies[proxy] = ProxyStatus(url=proxy)

    @property
    def healthy_proxies(self) -> list[str]:
        """Get list of healthy proxies."""
        return [
            url for url, status in self.pool.proxies.items()
            if status.is_healthy
        ]

    @property
    def all_proxies(self) -> list[ProxyStatus]:
        """Get all proxy statuses."""
        return list(self.pool.proxies.values())

    def get_next_proxy(self) -> Optional[str]:
        """Get next healthy proxy from the pool."""
        healthy = self.healthy_proxies

        if not healthy:
            # Try to recover - reset all proxies
            for status in self.pool.proxies.values():
                if status.fail_count < self.pool.max_fail_count * 2:
                    status.is_healthy = True
            healthy = self.healthy_proxies

        if not healthy:
            return None

        self.pool.current_index = (self.pool.current_index + 1) % len(healthy)
        return healthy[self.pool.current_index]

    def mark_success(self, proxy_url: str):
        """Mark a proxy as successful."""
        if proxy_url in self.pool.proxies:
            status = self.pool.proxies[proxy_url]
            status.success_count += 1
            status.fail_count = 0
            status.is_healthy = True
            status.last_error = None

    def mark_failure(self, proxy_url: str, error: str = None):
        """Mark a proxy as failed."""
        if proxy_url in self.pool.proxies:
            status = self.pool.proxies[proxy_url]
            status.fail_count += 1
            status.last_error = error

            if status.fail_count >= self.pool.max_fail_count:
                status.is_healthy = False

    async def check_proxy(self, proxy_url: str) -> bool:
        """Check if a single proxy is healthy."""
        status = self.pool.proxies.get(proxy_url)
        if not status:
            return False

        start_time = time.time()

        try:
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
            async with httpx.AsyncClient(
                transport=transport,
                timeout=self.pool.timeout
            ) as client:
                response = await client.get(self.pool.health_check_url)
                response.raise_for_status()

            elapsed_ms = (time.time() - start_time) * 1000
            status.is_healthy = True
            status.response_time_ms = elapsed_ms
            status.last_check = time.time()
            status.last_error = None
            return True

        except Exception as e:
            status.is_healthy = False
            status.last_check = time.time()
            status.last_error = str(e)
            return False

    async def check_all_proxies(self, progress_callback=None) -> dict[str, bool]:
        """Check all proxies and return results."""
        results = {}
        total = len(self.pool.proxies)

        for i, proxy_url in enumerate(self.pool.proxies.keys()):
            is_healthy = await self.check_proxy(proxy_url)
            results[proxy_url] = is_healthy

            if progress_callback:
                progress_callback(i + 1, total, proxy_url, is_healthy)

        return results

    async def check_stale_proxies(self) -> list[str]:
        """Check proxies that haven't been checked recently."""
        current_time = time.time()
        stale = []

        for proxy_url, status in self.pool.proxies.items():
            if current_time - status.last_check > self.pool.health_check_interval:
                stale.append(proxy_url)
                await self.check_proxy(proxy_url)

        return stale

    def add_proxy(self, proxy_url: str):
        """Add a new proxy to the pool."""
        if proxy_url not in self.pool.proxies:
            self.pool.proxies[proxy_url] = ProxyStatus(url=proxy_url)

    def remove_proxy(self, proxy_url: str):
        """Remove a proxy from the pool."""
        if proxy_url in self.pool.proxies:
            del self.pool.proxies[proxy_url]

    def reset_all(self):
        """Reset all proxies to healthy state."""
        for status in self.pool.proxies.values():
            status.is_healthy = True
            status.fail_count = 0
            status.last_error = None

    def get_statistics(self) -> dict:
        """Get overall proxy pool statistics."""
        total = len(self.pool.proxies)
        healthy = len(self.healthy_proxies)
        total_success = sum(s.success_count for s in self.pool.proxies.values())
        total_fail = sum(s.fail_count for s in self.pool.proxies.values())
        avg_response = sum(
            s.response_time_ms for s in self.pool.proxies.values() if s.response_time_ms > 0
        ) / max(1, sum(1 for s in self.pool.proxies.values() if s.response_time_ms > 0))

        return {
            "total": total,
            "healthy": healthy,
            "unhealthy": total - healthy,
            "total_successes": total_success,
            "total_failures": total_fail,
            "average_response_ms": round(avg_response, 2)
        }
