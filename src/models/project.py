"""Pydantic models for Parsonic project configuration."""

from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum


class SiteType(str, Enum):
    AUTO = "auto"
    STATIC = "static"
    JAVASCRIPT = "javascript"
    API = "api"


class RequestMethod(str, Enum):
    GET = "GET"
    POST = "POST"


class AuthType(str, Enum):
    NONE = "none"
    COOKIES = "cookies"
    BEARER = "bearer"
    BASIC = "basic"
    FORM = "form"
    SESSION = "session"


class SelectorField(BaseModel):
    """A single field to extract from the page."""
    name: str
    selector: str
    selector_type: str = "css"  # css or xpath
    attribute: Optional[str] = None  # None = text content, or 'href', 'src', etc.
    fallback_selectors: list[str] = Field(default_factory=list)
    transform: Optional[str] = None  # Python expression for transformation


class PaginationConfig(BaseModel):
    """Configuration for handling pagination."""
    enabled: bool = False
    type: str = "none"  # none, next_button, page_numbers, infinite_scroll, load_more, url_pattern
    selector: Optional[str] = None
    url_pattern: Optional[str] = None  # e.g., "page={page}"
    max_pages: int = 100
    wait_after_click: float = 2.0


class ProxyConfig(BaseModel):
    """Proxy configuration."""
    enabled: bool = False
    proxies: list[str] = Field(default_factory=list)
    rotate: bool = True
    health_check: bool = True


class AuthConfig(BaseModel):
    """Authentication configuration."""
    type: AuthType = AuthType.NONE
    cookies: Optional[str] = None
    bearer_token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    login_url: Optional[str] = None
    login_selector: Optional[str] = None


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    min_delay: float = 1.0
    max_delay: float = 3.0
    max_concurrent: int = 3
    adaptive: bool = True


class LinkFollowConfig(BaseModel):
    """Configuration for following links (crawl mode)."""
    enabled: bool = False
    link_selectors: list[str] = Field(default_factory=list)  # Multiple selectors supported
    max_depth: int = 1
    same_domain_only: bool = True

    def __init__(self, **data):
        # Backwards compatibility: convert old link_selector to link_selectors
        if 'link_selector' in data and 'link_selectors' not in data:
            old_selector = data.pop('link_selector')
            if old_selector:
                data['link_selectors'] = [old_selector]
        super().__init__(**data)


class TargetConfig(BaseModel):
    """Target URL configuration."""
    urls: list[str] = Field(default_factory=list)
    url_pattern: Optional[str] = None  # e.g., "https://example.com/page/{1-10}"
    site_type: SiteType = SiteType.AUTO
    method: RequestMethod = RequestMethod.GET
    headers: dict[str, str] = Field(default_factory=dict)


class ScraperProject(BaseModel):
    """Complete scraper project configuration."""
    name: str = "Untitled Project"
    version: str = "1.0"

    # Target
    target: TargetConfig = Field(default_factory=TargetConfig)

    # Extraction
    fields: list[SelectorField] = Field(default_factory=list)

    # Pagination
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)

    # Link following
    link_follow: LinkFollowConfig = Field(default_factory=LinkFollowConfig)

    # Auth & Proxy
    auth: AuthConfig = Field(default_factory=AuthConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)

    # Rate limiting
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    # Options
    respect_robots_txt: bool = True
    detect_duplicates: bool = True
    retry_count: int = 3
    timeout: float = 30.0

    def save(self, path: str) -> None:
        """Save project to JSON file."""
        with open(path, 'w') as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: str) -> "ScraperProject":
        """Load project from JSON file."""
        with open(path, 'r') as f:
            return cls.model_validate_json(f.read())
