"""Pre-built scraper templates for common site patterns."""

from src.models.project import (
    ScraperProject, TargetConfig, SelectorField, PaginationConfig,
    RateLimitConfig, SiteType
)


def create_ecommerce_product_template() -> ScraperProject:
    """Template for e-commerce product pages."""
    project = ScraperProject(
        name="E-commerce Product Scraper",
        target=TargetConfig(
            site_type=SiteType.JAVASCRIPT,
        ),
        fields=[
            SelectorField(
                name="title",
                selector="h1, .product-title, [data-testid='product-title']",
                fallback_selectors=["#productTitle", ".product-name"]
            ),
            SelectorField(
                name="price",
                selector=".price, .product-price, [data-testid='price']",
                fallback_selectors=[".current-price", "#priceblock_ourprice"]
            ),
            SelectorField(
                name="description",
                selector=".description, .product-description, #description",
                fallback_selectors=[".product-details", "[data-testid='description']"]
            ),
            SelectorField(
                name="image",
                selector=".product-image img, .gallery img",
                attribute="src",
                fallback_selectors=["#main-image", ".primary-image"]
            ),
            SelectorField(
                name="rating",
                selector=".rating, .star-rating, [data-testid='rating']",
                fallback_selectors=[".review-score", ".average-rating"]
            ),
            SelectorField(
                name="availability",
                selector=".availability, .stock-status, #availability",
                fallback_selectors=[".in-stock", ".out-of-stock"]
            ),
        ],
        rate_limit=RateLimitConfig(
            min_delay=2.0,
            max_delay=5.0,
            max_concurrent=2,
            adaptive=True
        )
    )
    return project


def create_news_article_template() -> ScraperProject:
    """Template for news article pages."""
    project = ScraperProject(
        name="News Article Scraper",
        target=TargetConfig(
            site_type=SiteType.STATIC,
        ),
        fields=[
            SelectorField(
                name="headline",
                selector="h1, .headline, .article-title",
                fallback_selectors=[".entry-title", "[data-testid='headline']"]
            ),
            SelectorField(
                name="author",
                selector=".author, .byline, [rel='author']",
                fallback_selectors=[".author-name", ".post-author"]
            ),
            SelectorField(
                name="date",
                selector="time, .date, .publish-date",
                attribute="datetime",
                fallback_selectors=[".article-date", ".post-date"]
            ),
            SelectorField(
                name="content",
                selector="article, .article-body, .post-content",
                fallback_selectors=[".entry-content", ".story-body"]
            ),
            SelectorField(
                name="category",
                selector=".category, .section, [data-category]",
                fallback_selectors=[".article-category", ".tag"]
            ),
            SelectorField(
                name="image",
                selector="article img, .featured-image img",
                attribute="src",
                fallback_selectors=[".article-image", ".hero-image"]
            ),
        ],
        rate_limit=RateLimitConfig(
            min_delay=1.0,
            max_delay=3.0,
            max_concurrent=3,
            adaptive=True
        )
    )
    return project


def create_job_listing_template() -> ScraperProject:
    """Template for job listing pages."""
    project = ScraperProject(
        name="Job Listing Scraper",
        target=TargetConfig(
            site_type=SiteType.JAVASCRIPT,
        ),
        fields=[
            SelectorField(
                name="title",
                selector=".job-title, h1, .position-title",
                fallback_selectors=["[data-testid='job-title']", ".listing-title"]
            ),
            SelectorField(
                name="company",
                selector=".company-name, .employer, [data-company]",
                fallback_selectors=[".organization", ".company"]
            ),
            SelectorField(
                name="location",
                selector=".location, .job-location, [data-location]",
                fallback_selectors=[".city", ".workplace"]
            ),
            SelectorField(
                name="salary",
                selector=".salary, .compensation, [data-salary]",
                fallback_selectors=[".pay-range", ".wage"]
            ),
            SelectorField(
                name="description",
                selector=".job-description, .description, #job-details",
                fallback_selectors=[".posting-description", ".details"]
            ),
            SelectorField(
                name="requirements",
                selector=".requirements, .qualifications, #requirements",
                fallback_selectors=[".skills-required", ".experience"]
            ),
            SelectorField(
                name="posted_date",
                selector=".posted-date, .date-posted, time",
                fallback_selectors=[".listing-date", ".publish-date"]
            ),
        ],
        rate_limit=RateLimitConfig(
            min_delay=2.0,
            max_delay=4.0,
            max_concurrent=2,
            adaptive=True
        )
    )
    return project


def create_real_estate_template() -> ScraperProject:
    """Template for real estate listing pages."""
    project = ScraperProject(
        name="Real Estate Scraper",
        target=TargetConfig(
            site_type=SiteType.JAVASCRIPT,
        ),
        fields=[
            SelectorField(
                name="address",
                selector=".address, .property-address, h1",
                fallback_selectors=["[data-address]", ".listing-address"]
            ),
            SelectorField(
                name="price",
                selector=".price, .listing-price, [data-price]",
                fallback_selectors=[".property-price", ".cost"]
            ),
            SelectorField(
                name="bedrooms",
                selector=".beds, .bedrooms, [data-beds]",
                fallback_selectors=[".bed-count", ".bedroom-count"]
            ),
            SelectorField(
                name="bathrooms",
                selector=".baths, .bathrooms, [data-baths]",
                fallback_selectors=[".bath-count", ".bathroom-count"]
            ),
            SelectorField(
                name="sqft",
                selector=".sqft, .square-feet, [data-sqft]",
                fallback_selectors=[".area", ".size"]
            ),
            SelectorField(
                name="description",
                selector=".description, .property-description, #description",
                fallback_selectors=[".listing-details", ".remarks"]
            ),
            SelectorField(
                name="images",
                selector=".gallery img, .photos img",
                attribute="src",
                fallback_selectors=[".property-images img", ".slider img"]
            ),
        ],
        rate_limit=RateLimitConfig(
            min_delay=3.0,
            max_delay=6.0,
            max_concurrent=2,
            adaptive=True
        )
    )
    return project


def create_social_profile_template() -> ScraperProject:
    """Template for social media profile pages."""
    project = ScraperProject(
        name="Social Profile Scraper",
        target=TargetConfig(
            site_type=SiteType.JAVASCRIPT,
        ),
        fields=[
            SelectorField(
                name="username",
                selector=".username, .handle, [data-username]",
                fallback_selectors=["@*", ".screen-name"]
            ),
            SelectorField(
                name="display_name",
                selector=".display-name, .name, h1",
                fallback_selectors=[".full-name", ".profile-name"]
            ),
            SelectorField(
                name="bio",
                selector=".bio, .description, .about",
                fallback_selectors=[".profile-bio", ".user-description"]
            ),
            SelectorField(
                name="followers",
                selector=".followers, [data-followers]",
                fallback_selectors=[".follower-count", ".fans"]
            ),
            SelectorField(
                name="following",
                selector=".following, [data-following]",
                fallback_selectors=[".following-count", ".friends"]
            ),
            SelectorField(
                name="avatar",
                selector=".avatar img, .profile-image img",
                attribute="src",
                fallback_selectors=[".user-avatar", ".profile-pic"]
            ),
        ],
        rate_limit=RateLimitConfig(
            min_delay=3.0,
            max_delay=7.0,
            max_concurrent=1,
            adaptive=True
        )
    )
    return project


def create_business_directory_template() -> ScraperProject:
    """Template for business directory sites (Yellow Pages, Yelp, Chamber of Commerce)."""
    project = ScraperProject(
        name="Business Directory Scraper",
        target=TargetConfig(
            site_type=SiteType.JAVASCRIPT,
        ),
        fields=[
            SelectorField(
                name="company_name",
                selector="h1, .business-name, [data-business-name], .listing-title",
                fallback_selectors=[".company-name", ".org-name", ".name"]
            ),
            SelectorField(
                name="phone",
                selector='a[href^="tel:"], .phone, .telephone',
                attribute="href",
                fallback_selectors=[".phone-number", "[data-phone]", ".contact-phone"]
            ),
            SelectorField(
                name="email",
                selector='a[href^="mailto:"], .email',
                attribute="href",
                fallback_selectors=["[data-email]", ".contact-email"]
            ),
            SelectorField(
                name="address",
                selector=".address, address, [data-address], .location",
                fallback_selectors=[".street-address", ".full-address"]
            ),
            SelectorField(
                name="website",
                selector='a.website, a[rel="external"], [data-website]',
                attribute="href",
                fallback_selectors=[".company-url", ".external-link"]
            ),
            SelectorField(
                name="description",
                selector=".description, .about, .summary, .business-description",
                fallback_selectors=["[data-description]", ".overview"]
            ),
            SelectorField(
                name="rating",
                selector=".rating, .stars, [data-rating], .review-score",
                fallback_selectors=[".average-rating", ".star-rating"]
            ),
            SelectorField(
                name="category",
                selector=".category, .industry, [data-category], .business-type",
                fallback_selectors=[".sector", ".vertical"]
            ),
        ],
        rate_limit=RateLimitConfig(
            min_delay=2.0,
            max_delay=5.0,
            max_concurrent=2,
            adaptive=True
        )
    )
    return project


def create_company_profile_template() -> ScraperProject:
    """Template for company profile pages (Crunchbase, LinkedIn Company, etc.)."""
    project = ScraperProject(
        name="Company Profile Scraper",
        target=TargetConfig(
            site_type=SiteType.JAVASCRIPT,
        ),
        fields=[
            SelectorField(
                name="company_name",
                selector="h1, .company-name, [data-company], .org-name",
                fallback_selectors=[".profile-name", ".organization-name"]
            ),
            SelectorField(
                name="description",
                selector=".description, .about, .summary, [data-description]",
                fallback_selectors=[".company-overview", ".bio", ".tagline"]
            ),
            SelectorField(
                name="founded",
                selector=".founded, [data-founded], .year-founded",
                fallback_selectors=[".established", ".founding-date"]
            ),
            SelectorField(
                name="employees",
                selector=".employees, .company-size, [data-employees]",
                fallback_selectors=[".employee-count", ".headcount", ".team-size"]
            ),
            SelectorField(
                name="industry",
                selector=".industry, [data-industry], .sector",
                fallback_selectors=[".category", ".vertical", ".market"]
            ),
            SelectorField(
                name="headquarters",
                selector=".headquarters, .hq, [data-hq], .location",
                fallback_selectors=[".address", ".office-location"]
            ),
            SelectorField(
                name="website",
                selector='.website a, [data-website], a[rel="external"]',
                attribute="href",
                fallback_selectors=["a.company-website", ".company-url"]
            ),
            SelectorField(
                name="linkedin_url",
                selector='a[href*="linkedin.com/company"]',
                attribute="href",
            ),
            SelectorField(
                name="funding",
                selector=".funding, [data-funding], .total-raised",
                fallback_selectors=[".investment", ".capital-raised", ".funding-amount"]
            ),
            SelectorField(
                name="revenue",
                selector=".revenue, [data-revenue], .annual-revenue",
                fallback_selectors=[".income", ".sales"]
            ),
        ],
        rate_limit=RateLimitConfig(
            min_delay=3.0,
            max_delay=7.0,
            max_concurrent=1,
            adaptive=True
        )
    )
    return project


def create_contact_person_template() -> ScraperProject:
    """Template for contact/person pages (LinkedIn profiles, team pages, etc.)."""
    project = ScraperProject(
        name="Contact/Person Scraper",
        target=TargetConfig(
            site_type=SiteType.JAVASCRIPT,
        ),
        fields=[
            SelectorField(
                name="full_name",
                selector="h1, .name, .full-name, [data-name]",
                fallback_selectors=[".person-name", ".profile-name", ".display-name"]
            ),
            SelectorField(
                name="job_title",
                selector=".title, .job-title, .position, [data-title]",
                fallback_selectors=[".headline", ".role", ".designation"]
            ),
            SelectorField(
                name="company",
                selector=".company, .organization, [data-company]",
                fallback_selectors=[".employer", ".works-at", ".current-company"]
            ),
            SelectorField(
                name="email",
                selector='a[href^="mailto:"], .email, [data-email]',
                attribute="href",
                fallback_selectors=[".contact-email", ".personal-email"]
            ),
            SelectorField(
                name="phone",
                selector='a[href^="tel:"], .phone, [data-phone]',
                attribute="href",
                fallback_selectors=[".telephone", ".mobile", ".contact-phone"]
            ),
            SelectorField(
                name="linkedin_url",
                selector='a[href*="linkedin.com/in/"]',
                attribute="href",
            ),
            SelectorField(
                name="twitter_url",
                selector='a[href*="twitter.com"], a[href*="x.com"]',
                attribute="href",
            ),
            SelectorField(
                name="location",
                selector=".location, [data-location], .city",
                fallback_selectors=[".address", ".region", ".area"]
            ),
            SelectorField(
                name="bio",
                selector=".bio, .about, .summary",
                fallback_selectors=[".description", ".profile-summary", ".about-me"]
            ),
        ],
        rate_limit=RateLimitConfig(
            min_delay=3.0,
            max_delay=7.0,
            max_concurrent=1,
            adaptive=True
        )
    )
    return project


# Template registry
TEMPLATES = {
    # Business templates (most relevant for B2B data)
    "business_directory": {
        "name": "Business Directory",
        "description": "Scrape businesses from directory sites (Yellow Pages, Yelp, Chamber of Commerce)",
        "create": create_business_directory_template
    },
    "company_profile": {
        "name": "Company Profile",
        "description": "Scrape company profiles (Crunchbase, LinkedIn Company pages)",
        "create": create_company_profile_template
    },
    "contact_person": {
        "name": "Contact/Person",
        "description": "Scrape contact details and person profiles",
        "create": create_contact_person_template
    },
    # Other templates
    "ecommerce": {
        "name": "E-commerce Product",
        "description": "Scrape product details from online stores",
        "create": create_ecommerce_product_template
    },
    "news": {
        "name": "News Article",
        "description": "Scrape articles from news websites",
        "create": create_news_article_template
    },
    "jobs": {
        "name": "Job Listing",
        "description": "Scrape job postings from career sites",
        "create": create_job_listing_template
    },
    "realestate": {
        "name": "Real Estate",
        "description": "Scrape property listings",
        "create": create_real_estate_template
    },
    "social": {
        "name": "Social Profile",
        "description": "Scrape social media profiles",
        "create": create_social_profile_template
    },
}


def get_template(template_id: str) -> ScraperProject:
    """Get a template project by ID."""
    if template_id in TEMPLATES:
        return TEMPLATES[template_id]["create"]()
    raise ValueError(f"Unknown template: {template_id}")


def list_templates() -> list[dict]:
    """List all available templates."""
    return [
        {
            "id": tid,
            "name": info["name"],
            "description": info["description"]
        }
        for tid, info in TEMPLATES.items()
    ]
