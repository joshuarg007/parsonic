"""
LLM-powered enrichment for Parsonic scraper.

Uses local LLMs (via Ollama) for:
1. Business classification (products vs services, employee count)
2. Selector recovery (generate new CSS selectors when extraction fails)
3. Entity normalization (deduplicate and canonicalize company records)

Respects thermal limits - pauses inference when system is hot.
"""

import json
import re
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from enum import Enum

# Thermal monitoring integration
from src.core.thermal_monitor import is_thermal_safe, get_thermal_status, ThermalState


class BusinessType(Enum):
    """Type of business."""
    PRODUCTS = "products"
    SERVICES = "services"
    BOTH = "both"
    UNKNOWN = "unknown"


class EmployeeBucket(Enum):
    """Employee count ranges."""
    TINY = "1-10"
    SMALL = "11-50"
    MEDIUM = "51-200"
    LARGE = "201-1000"
    ENTERPRISE = "1000+"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of business classification."""
    business_type: BusinessType = BusinessType.UNKNOWN
    employee_bucket: EmployeeBucket = EmployeeBucket.UNKNOWN
    confidence: float = 0.0
    evidence: List[Dict[str, str]] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class SelectorSuggestion:
    """Suggested CSS selector from LLM."""
    field_name: str
    selector: str
    confidence: float = 0.0
    fallback_selectors: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class NormalizedEntity:
    """Canonicalized company/entity record."""
    legal_name: str = ""
    brand_name: str = ""
    domain: str = ""
    hq_city: str = ""
    hq_state: str = ""
    hq_country: str = ""
    industry: str = ""
    is_b2b: Optional[bool] = None
    confidence: float = 0.0
    source_variants: List[str] = field(default_factory=list)


@dataclass
class DetectedField:
    """Field detected by AI page analysis."""
    name: str
    selector: str
    sample_value: str = ""
    confidence: float = 0.0
    field_type: str = "text"  # text, link, email, phone, address
    attribute: Optional[str] = None  # None for text, "href" for links


@dataclass
class LLMConfig:
    """Configuration for LLM enrichment."""
    # Ollama settings
    ollama_host: str = "http://localhost:11434"

    # Model selection
    classification_model: str = "qwen2.5:7b"
    selector_model: str = "qwen2.5-coder:7b"
    normalization_model: str = "qwen2.5:7b"

    # Generation settings
    temperature: float = 0.3  # Low for deterministic output
    max_tokens: int = 1024
    timeout: float = 30.0

    # Caching
    cache_dir: Optional[Path] = None
    cache_ttl_hours: int = 24 * 7  # 1 week

    # Thermal safety
    thermal_wait_seconds: float = 30.0  # Wait time when paused
    max_thermal_retries: int = 10


class LLMEnrichment:
    """
    LLM-powered data enrichment with thermal safety.

    Usage:
        enricher = LLMEnrichment()

        # Classify a business
        result = enricher.classify_business(page_text)
        print(f"Type: {result.business_type}, Employees: {result.employee_bucket}")

        # Recover broken selectors
        selectors = enricher.suggest_selectors(html, ["company_name", "phone", "email"])

        # Normalize entities
        canonical = enricher.normalize_entity({"name": "IBM Corp", "website": "ibm.com"})
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._session = None
        self._selector_cache: Dict[str, List[SelectorSuggestion]] = {}

        # Setup cache directory
        if self.config.cache_dir:
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)

    def _wait_for_thermal_safety(self) -> bool:
        """Wait for system to cool down if needed. Returns True if safe to proceed."""
        retries = 0
        while retries < self.config.max_thermal_retries:
            if is_thermal_safe():
                return True

            status = get_thermal_status()
            print(f"[LLM] Thermal pause - {status.reason}. Waiting {self.config.thermal_wait_seconds}s...")
            time.sleep(self.config.thermal_wait_seconds)
            retries += 1

        print(f"[LLM] Thermal timeout after {retries} retries")
        return False

    def _call_ollama(self, model: str, prompt: str, system: str = "") -> Optional[str]:
        """Call Ollama API with thermal safety checks."""
        if not self._wait_for_thermal_safety():
            return None

        try:
            import requests

            url = f"{self.config.ollama_host}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                }
            }

            response = requests.post(
                url,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            result = response.json()
            return result.get("response", "")

        except requests.exceptions.ConnectionError:
            print(f"[LLM] Ollama not running at {self.config.ollama_host}")
            print(f"[LLM] Start with: ollama serve")
            return None
        except Exception as e:
            # Check if thermal kill
            error_msg = str(e).lower()
            if any(x in error_msg for x in ['connection', 'reset', 'refused', 'closed', 'eof']):
                print(f"[LLM] Connection lost (possible thermal kill): {e}")
            else:
                print(f"[LLM] Ollama error: {e}")
            return None

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Extract JSON from LLM response."""
        if not response:
            return None

        # Try to find JSON in response
        try:
            # First try direct parse
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def classify_business(self, page_text: str, url: str = "") -> ClassificationResult:
        """
        Classify a business based on page content.

        Args:
            page_text: Cleaned text content from the page
            url: Optional URL for context

        Returns:
            ClassificationResult with business type, employee bucket, confidence, and evidence
        """
        result = ClassificationResult()

        # Truncate text to reasonable size
        max_chars = 4000
        if len(page_text) > max_chars:
            page_text = page_text[:max_chars] + "\n[truncated]"

        system_prompt = """You are a business analyst. Analyze the provided webpage content and classify the business.

Output valid JSON only with this exact structure:
{
    "business_type": "products" | "services" | "both" | "unknown",
    "employee_bucket": "1-10" | "11-50" | "51-200" | "201-1000" | "1000+" | "unknown",
    "confidence": 0.0-1.0,
    "evidence": [
        {"field": "business_type", "snippet": "exact quote from text", "weight": "strong|moderate|weak"},
        {"field": "employee_bucket", "snippet": "exact quote from text", "weight": "strong|moderate|weak"}
    ]
}

Rules:
- business_type: "products" if they sell physical/digital products, "services" if they provide services, "both" if mixed
- employee_bucket: Look for phrases like "team of X", "X employees", company size indicators
- confidence: Your certainty (0.9+ needs strong evidence, 0.5-0.7 for reasonable inference)
- evidence: Quote the EXACT text that led to each decision"""

        user_prompt = f"""URL: {url}

Page content:
{page_text}

Classify this business. Output JSON only."""

        response = self._call_ollama(
            self.config.classification_model,
            user_prompt,
            system_prompt
        )

        result.raw_response = response or ""

        parsed = self._parse_json_response(response)
        if parsed:
            # Map business type
            bt = parsed.get("business_type", "unknown").lower()
            result.business_type = {
                "products": BusinessType.PRODUCTS,
                "services": BusinessType.SERVICES,
                "both": BusinessType.BOTH,
            }.get(bt, BusinessType.UNKNOWN)

            # Map employee bucket
            eb = parsed.get("employee_bucket", "unknown")
            result.employee_bucket = {
                "1-10": EmployeeBucket.TINY,
                "11-50": EmployeeBucket.SMALL,
                "51-200": EmployeeBucket.MEDIUM,
                "201-1000": EmployeeBucket.LARGE,
                "1000+": EmployeeBucket.ENTERPRISE,
            }.get(eb, EmployeeBucket.UNKNOWN)

            result.confidence = float(parsed.get("confidence", 0.0))
            result.evidence = parsed.get("evidence", [])

        return result

    def suggest_selectors(
        self,
        html: str,
        field_names: List[str],
        failed_selectors: Optional[Dict[str, str]] = None,
        domain: str = ""
    ) -> List[SelectorSuggestion]:
        """
        Generate CSS selectors for fields when extraction fails.

        Args:
            html: HTML content of the page
            field_names: List of field names to extract
            failed_selectors: Previous selectors that didn't work
            domain: Domain for cache key

        Returns:
            List of SelectorSuggestion for each field
        """
        # Check cache first
        cache_key = self._get_selector_cache_key(html, field_names, domain)
        if cache_key in self._selector_cache:
            return self._selector_cache[cache_key]

        # Simplify HTML for prompt (remove scripts, styles, keep structure)
        simplified_html = self._simplify_html(html)

        # Truncate if too long
        max_chars = 6000
        if len(simplified_html) > max_chars:
            simplified_html = simplified_html[:max_chars] + "\n<!-- truncated -->"

        failed_info = ""
        if failed_selectors:
            failed_info = "\nPrevious selectors that FAILED (do not reuse):\n"
            for field, selector in failed_selectors.items():
                failed_info += f"  {field}: {selector}\n"

        system_prompt = """You are a web scraping expert. Generate CSS selectors for extracting data from HTML.

Output valid JSON only with this structure:
{
    "selectors": [
        {
            "field": "field_name",
            "selector": "CSS selector",
            "confidence": 0.0-1.0,
            "fallbacks": ["alt selector 1", "alt selector 2"],
            "reasoning": "why this selector works"
        }
    ]
}

Rules:
- Prefer stable selectors: IDs, data-* attributes, semantic classes
- Avoid fragile selectors: nth-child, overly specific paths
- For each field, provide 2-3 fallback selectors
- Confidence based on selector stability (ID=0.9+, data-attr=0.8+, class=0.6-0.8)"""

        user_prompt = f"""Extract these fields: {', '.join(field_names)}
{failed_info}
HTML structure:
{simplified_html}

Generate CSS selectors. Output JSON only."""

        response = self._call_ollama(
            self.config.selector_model,
            user_prompt,
            system_prompt
        )

        suggestions = []
        parsed = self._parse_json_response(response)

        if parsed and "selectors" in parsed:
            for item in parsed["selectors"]:
                suggestions.append(SelectorSuggestion(
                    field_name=item.get("field", ""),
                    selector=item.get("selector", ""),
                    confidence=float(item.get("confidence", 0.0)),
                    fallback_selectors=item.get("fallbacks", []),
                    reasoning=item.get("reasoning", "")
                ))

        # Cache results
        if suggestions:
            self._selector_cache[cache_key] = suggestions

        return suggestions

    def normalize_entity(self, entity_data: Dict[str, Any]) -> NormalizedEntity:
        """
        Normalize and canonicalize an entity record.

        Args:
            entity_data: Raw scraped entity data

        Returns:
            NormalizedEntity with canonical fields
        """
        result = NormalizedEntity()
        result.source_variants = [str(v) for v in entity_data.values() if v]

        # Build entity string for analysis
        entity_str = json.dumps(entity_data, indent=2)

        system_prompt = """You are a data normalization expert. Canonicalize the entity record.

Output valid JSON only with this structure:
{
    "legal_name": "Full legal company name",
    "brand_name": "Common brand/trade name",
    "domain": "primary domain without www",
    "hq_city": "Headquarters city",
    "hq_state": "State/province code",
    "hq_country": "Country code (US, UK, etc)",
    "industry": "Primary industry category",
    "is_b2b": true/false/null,
    "confidence": 0.0-1.0
}

Rules:
- legal_name: Official registered name (Inc, LLC, Corp, etc)
- brand_name: What customers call it
- domain: Extract from website/email, normalize (no www, https)
- is_b2b: true if primarily B2B, false if B2C, null if unclear
- Normalize all text: proper capitalization, consistent formatting"""

        user_prompt = f"""Normalize this entity:
{entity_str}

Output JSON only."""

        response = self._call_ollama(
            self.config.normalization_model,
            user_prompt,
            system_prompt
        )

        parsed = self._parse_json_response(response)
        if parsed:
            result.legal_name = parsed.get("legal_name", "")
            result.brand_name = parsed.get("brand_name", "")
            result.domain = parsed.get("domain", "")
            result.hq_city = parsed.get("hq_city", "")
            result.hq_state = parsed.get("hq_state", "")
            result.hq_country = parsed.get("hq_country", "")
            result.industry = parsed.get("industry", "")
            result.is_b2b = parsed.get("is_b2b")
            result.confidence = float(parsed.get("confidence", 0.0))

        return result

    def analyze_page_fields(self, html: str, url: str = "") -> List[DetectedField]:
        """
        AI-powered page analysis to detect business fields.

        Sends simplified HTML to LLM, asks it to identify all business-relevant
        fields with CSS selectors.

        Args:
            html: Full HTML content of the page
            url: Optional URL for context

        Returns:
            List of DetectedField with selectors for each detected field
        """
        # Simplify HTML for prompt
        simplified_html = self._simplify_html(html)

        # Truncate if too long
        max_chars = 8000
        if len(simplified_html) > max_chars:
            simplified_html = simplified_html[:max_chars] + "\n<!-- truncated -->"

        system_prompt = """You are a web scraping expert. Analyze the PROVIDED HTML and extract CSS selectors for business data.

CRITICAL: You MUST derive selectors from the ACTUAL HTML provided. Do NOT invent or guess selectors.
- Look at the actual class names, IDs, and tag structures in the HTML
- The selector must match elements that EXIST in the provided HTML
- Include the actual text content you found as sample_value

Output valid JSON only:
{
    "fields": [
        {
            "name": "field_name_snake_case",
            "selector": "actual CSS selector from the HTML",
            "sample_value": "actual text found in that element",
            "confidence": 0.0-1.0,
            "field_type": "text|link|email|phone|address",
            "attribute": null or "href" or "src"
        }
    ]
}

Field types to look for:
- company_name - Main business/company name (often in h1, h2, or prominent element)
- phone - Phone numbers (look for tel: links or text with digits)
- email - Email addresses (look for mailto: links or @ symbols)
- address - Physical addresses
- website - Website URLs (look for http links)
- description - Business descriptions
- rating - Ratings or stars
- category - Business category/industry

Selector strategy:
1. First look for IDs: #company-name, #phone, etc.
2. Then data attributes: [data-field="phone"], [itemprop="telephone"]
3. Then specific classes that exist in the HTML
4. Use tag + class combinations: h1.title, span.phone
5. NEVER invent class names - only use what's in the HTML

Example: If HTML has <h2 class="biz-name">Acme Corp</h2>, use selector "h2.biz-name" not ".company-name"."""

        user_prompt = f"""URL: {url}

Analyze this HTML and find business data fields. Use ONLY selectors that match elements in this HTML:

{simplified_html}

Return JSON with selectors derived from the actual HTML above. Do not guess or invent class names."""

        response = self._call_ollama(
            self.config.selector_model,  # Use coder model for better selector generation
            user_prompt,
            system_prompt
        )

        fields = []
        parsed = self._parse_json_response(response)

        if parsed and "fields" in parsed:
            for item in parsed["fields"]:
                try:
                    fields.append(DetectedField(
                        name=item.get("name", "unknown"),
                        selector=item.get("selector", ""),
                        sample_value=item.get("sample_value", ""),
                        confidence=float(item.get("confidence", 0.0)),
                        field_type=item.get("field_type", "text"),
                        attribute=item.get("attribute")
                    ))
                except (ValueError, TypeError):
                    continue

        return fields

    def batch_normalize(
        self,
        entities: List[Dict[str, Any]],
        batch_size: int = 5
    ) -> List[NormalizedEntity]:
        """
        Normalize multiple entities in batches.

        Args:
            entities: List of raw entity data
            batch_size: Entities per LLM call

        Returns:
            List of NormalizedEntity
        """
        results = []

        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]

            for entity in batch:
                result = self.normalize_entity(entity)
                results.append(result)

                # Check thermal between each call
                if not is_thermal_safe():
                    print(f"[LLM] Pausing batch normalization due to thermal limits")
                    self._wait_for_thermal_safety()

        return results

    def _simplify_html(self, html: str) -> str:
        """Remove scripts, styles, and simplify HTML for LLM analysis."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for tag in soup(['script', 'style', 'noscript', 'iframe', 'svg']):
                tag.decompose()

            # Remove comments
            from bs4 import Comment
            for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
                comment.extract()

            # Get simplified HTML
            return soup.prettify()

        except ImportError:
            # Fallback: basic regex cleanup
            html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
            html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
            html = re.sub(r'<!--[\s\S]*?-->', '', html)
            return html

    def _get_selector_cache_key(
        self,
        html: str,
        field_names: List[str],
        domain: str
    ) -> str:
        """Generate cache key for selector suggestions."""
        # Hash HTML structure (not content) for cache key
        structure_hash = hashlib.md5(
            self._simplify_html(html)[:2000].encode()
        ).hexdigest()[:8]

        fields_hash = hashlib.md5(
            ','.join(sorted(field_names)).encode()
        ).hexdigest()[:8]

        return f"{domain}:{structure_hash}:{fields_hash}"

    def check_ollama_available(self) -> Tuple[bool, str]:
        """Check if Ollama is running and models are available."""
        try:
            import requests

            # Check server
            response = requests.get(
                f"{self.config.ollama_host}/api/tags",
                timeout=5
            )
            response.raise_for_status()

            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]

            # Check if our models are available
            needed = [
                self.config.classification_model,
                self.config.selector_model,
                self.config.normalization_model
            ]

            missing = []
            for model in set(needed):
                # Check if model or its base is available
                model_base = model.split(':')[0]
                if not any(model_base in m for m in models):
                    missing.append(model)

            if missing:
                return False, f"Missing models: {', '.join(missing)}. Run: ollama pull {missing[0]}"

            return True, f"Ollama ready with {len(models)} models"

        except requests.exceptions.ConnectionError:
            return False, f"Ollama not running. Start with: ollama serve"
        except Exception as e:
            return False, f"Ollama error: {e}"


# Module-level convenience functions
_enricher: Optional[LLMEnrichment] = None


def get_enricher(config: Optional[LLMConfig] = None) -> LLMEnrichment:
    """Get or create the LLM enrichment instance."""
    global _enricher
    if _enricher is None:
        _enricher = LLMEnrichment(config)
    return _enricher


def classify_business(page_text: str, url: str = "") -> ClassificationResult:
    """Classify a business from page content."""
    return get_enricher().classify_business(page_text, url)


def suggest_selectors(
    html: str,
    field_names: List[str],
    failed_selectors: Optional[Dict[str, str]] = None
) -> List[SelectorSuggestion]:
    """Generate CSS selectors for fields."""
    return get_enricher().suggest_selectors(html, field_names, failed_selectors)


def normalize_entity(entity_data: Dict[str, Any]) -> NormalizedEntity:
    """Normalize an entity record."""
    return get_enricher().normalize_entity(entity_data)


def analyze_page_fields(html: str, url: str = "") -> List[DetectedField]:
    """Analyze page HTML and detect business fields with selectors."""
    return get_enricher().analyze_page_fields(html, url)


# Quick test
if __name__ == "__main__":
    print("=" * 60)
    print("LLM Enrichment Test")
    print("=" * 60)

    enricher = LLMEnrichment()

    # Check Ollama
    available, message = enricher.check_ollama_available()
    print(f"\nOllama: {message}")

    if not available:
        print("\nTo set up Ollama:")
        print("  1. Install: curl -fsSL https://ollama.com/install.sh | sh")
        print("  2. Start: ollama serve")
        print("  3. Pull models:")
        print(f"     ollama pull {enricher.config.classification_model}")
        print(f"     ollama pull {enricher.config.selector_model}")
    else:
        # Test classification
        print("\nTesting classification...")
        test_text = """
        Acme Corp - Enterprise Software Solutions
        We help businesses streamline their operations with our suite of B2B tools.
        Our team of 150+ engineers builds world-class software.
        Contact us for a demo.
        """

        result = enricher.classify_business(test_text, "https://acme.example.com")
        print(f"  Business Type: {result.business_type.value}")
        print(f"  Employee Bucket: {result.employee_bucket.value}")
        print(f"  Confidence: {result.confidence:.2f}")

        if result.evidence:
            print("  Evidence:")
            for ev in result.evidence[:2]:
                print(f"    - {ev.get('field')}: \"{ev.get('snippet', '')[:50]}...\"")

    # Check thermal status
    from src.core.thermal_monitor import get_thermal_status
    status = get_thermal_status()
    print(f"\nThermal Status: {status.state.value}")
    print(f"  CPU: {status.cpu_temp or 'N/A'}°C")
    print(f"  GPU: {status.gpu_temp or 'N/A'}°C")
    print(f"  Safe for AI: {status.is_safe}")

    print("\n[OK] LLM Enrichment ready")
