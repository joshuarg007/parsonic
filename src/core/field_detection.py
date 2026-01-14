"""Smart field detection for business data scraping."""

import re
from typing import Optional


# Common patterns for business data fields
FIELD_PATTERNS = {
    # Contact patterns (highest priority for business scraping)
    "email": {
        "selectors": ['a[href^="mailto:"]', '[data-email]', '.email', '.contact-email'],
        "content_patterns": [r'\b[\w.-]+@[\w.-]+\.\w{2,}\b'],
        "attribute": "href",
        "transform": "regex_extract",
        "transform_pattern": r'mailto:(.*)',
        "priority": 100,
    },
    "phone": {
        "selectors": ['a[href^="tel:"]', '[data-phone]', '.phone', '.telephone'],
        "content_patterns": [r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'],
        "attribute": "href",
        "transform": "regex_replace",
        "transform_pattern": r'^tel:',
        "priority": 95,
    },
    "website": {
        "selectors": ['a.website', '[data-website]', '.company-website'],
        "content_patterns": [r'https?://[\w.-]+\.\w{2,}'],
        "attribute": "href",
        "priority": 80,
    },

    # Social media links
    "linkedin_url": {
        "selectors": ['a[href*="linkedin.com"]'],
        "attribute": "href",
        "priority": 70,
    },
    "twitter_url": {
        "selectors": ['a[href*="twitter.com"]', 'a[href*="x.com"]'],
        "attribute": "href",
        "priority": 70,
    },
    "facebook_url": {
        "selectors": ['a[href*="facebook.com"]'],
        "attribute": "href",
        "priority": 70,
    },

    # Company information
    "company_name": {
        "selectors": ['h1', '.company-name', '[data-company]', '.org-name', '.business-name'],
        "context_hints": ["company", "organization", "business", "firm"],
        "priority": 90,
    },
    "description": {
        "selectors": ['.description', '.about', '.summary', '[data-description]', '.bio'],
        "context_hints": ["about", "description", "overview", "summary"],
        "priority": 60,
    },
    "industry": {
        "selectors": ['.industry', '[data-industry]', '.sector', '.category'],
        "context_hints": ["industry", "sector", "category", "vertical"],
        "priority": 50,
    },
    "employees": {
        "selectors": ['.employees', '.company-size', '[data-employees]', '.headcount'],
        "content_patterns": [r'\d+[\s-]+\d+\s*employees', r'\d+\+?\s*employees'],
        "priority": 50,
    },
    "revenue": {
        "selectors": ['.revenue', '[data-revenue]', '.annual-revenue'],
        "content_patterns": [r'\$[\d,]+[MBK]?', r'Revenue:\s*\$'],
        "priority": 40,
    },
    "founded": {
        "selectors": ['.founded', '[data-founded]', '.year-founded', '.established'],
        "content_patterns": [r'Founded:?\s*\d{4}', r'Est\.?\s*\d{4}'],
        "priority": 40,
    },

    # Address components
    "address": {
        "selectors": [
            '.address', '[data-address]', 'address', '.location', '.street-address',
            '[itemprop="address"]', '.contact-address', '.business-address',
            '.company-address', '.office-address', '.hq-address'
        ],
        "context_hints": ["address", "location", "headquarters", "office", "hq", "located"],
        "content_patterns": [
            r'^\d+\s+[\w\s]+(ST|AVE|BLVD|RD|DR|LN|CT|WAY|PL|STREET|AVENUE|ROAD|DRIVE|LANE|HIGHWAY|HWY)\b',  # Street address
            r'\d+\s+\w+.*,\s*[A-Z]{2},?\s*\d{5}',  # Full address with city, state, zip
            r',\s*[A-Z][a-z]+,\s*[A-Z]{2},?\s*\d{5}',  # City, State ZIP pattern
            r'\d+\s+[A-Z][\w\s]+(?:Suite|Ste|Unit|Apt|#)\s*\d+',  # Address with suite/unit
        ],
        "priority": 85,  # Higher priority for business scraping
    },
    "city": {
        "selectors": ['.city', '[data-city]', '.locality'],
        "priority": 30,
    },
    "state": {
        "selectors": ['.state', '[data-state]', '.region'],
        "priority": 30,
    },
    "zip": {
        "selectors": ['.zip', '.postal-code', '[data-zip]', '.zipcode'],
        "content_patterns": [r'^\d{5}(-\d{4})?$'],  # Only match if JUST a zip code
        "priority": 30,
    },

    # Person/contact information
    "person_name": {
        "selectors": ['.name', '.person-name', '.full-name', '[data-name]'],
        "context_hints": ["name", "contact", "person", "representative"],
        "priority": 85,
    },
    "job_title": {
        "selectors": ['.title', '.job-title', '.position', '[data-title]', '.role'],
        "context_hints": ["title", "position", "role", "designation"],
        "priority": 65,
    },

    # Ratings/reviews
    "rating": {
        "selectors": ['.rating', '.stars', '[data-rating]', '.review-score'],
        "content_patterns": [r'\d\.?\d?\s*(?:out of|/)?\s*5', r'★'],
        "priority": 45,
    },
    "review_count": {
        "selectors": ['.reviews', '.review-count', '[data-reviews]'],
        "content_patterns": [r'\d+\s*reviews?'],
        "priority": 35,
    },
}


# Smart selectors for auto-detection
SMART_SELECTORS = {
    "email": {
        "primary": 'a[href^="mailto:"]',
        "fallbacks": ['[data-email]', '.email', '.contact-email'],
        "extract": "href",
    },
    "phone": {
        "primary": 'a[href^="tel:"]',
        "fallbacks": ['[data-phone]', '.phone', '.telephone'],
        "extract": "href",
    },
    "linkedin_url": {
        "primary": 'a[href*="linkedin.com"]',
        "fallbacks": ['[data-linkedin]', '.linkedin-link'],
        "extract": "href",
    },
    "twitter_url": {
        "primary": 'a[href*="twitter.com"], a[href*="x.com"]',
        "fallbacks": ['[data-twitter]', '.twitter-link'],
        "extract": "href",
    },
    "facebook_url": {
        "primary": 'a[href*="facebook.com"]',
        "fallbacks": ['[data-facebook]', '.facebook-link'],
        "extract": "href",
    },
    "website": {
        "primary": 'a[rel="external"], a.website, a.external-link',
        "fallbacks": ['[data-website]', '.company-url'],
        "extract": "href",
    },
}


def suggest_field_name(element_info: dict) -> list[dict]:
    """
    Analyze element and return ranked field name suggestions.

    Args:
        element_info: Dictionary containing element metadata:
            - tag: HTML tag name (e.g., 'a', 'div', 'span')
            - classes: List of CSS classes
            - id: Element ID
            - href: href attribute value (for links)
            - src: src attribute value (for images)
            - text: Text content
            - parent_classes: Parent element classes
            - nearby_text: Text from parent/siblings

    Returns:
        List of suggestions sorted by confidence:
        [
            {"name": "email", "confidence": 0.95, "attribute": "href", "reason": "mailto: link"},
            {"name": "contact_email", "confidence": 0.8, "reason": "class contains 'email'"},
        ]
    """
    suggestions = []

    tag = element_info.get("tag", "").lower()
    classes = element_info.get("classes", [])
    classes_str = " ".join(classes).lower()
    element_id = element_info.get("id", "").lower()
    href = element_info.get("href", "") or ""
    text = element_info.get("text", "") or ""
    parent_classes = element_info.get("parent_classes", [])
    parent_classes_str = " ".join(parent_classes).lower()

    # Check mailto: links first (highest confidence for email)
    if href.startswith("mailto:"):
        suggestions.append({
            "name": "email",
            "confidence": 0.98,
            "attribute": "href",
            "reason": "mailto: link detected"
        })

    # Check tel: links (highest confidence for phone)
    elif href.startswith("tel:"):
        suggestions.append({
            "name": "phone",
            "confidence": 0.98,
            "attribute": "href",
            "reason": "tel: link detected"
        })

    # Check social media links
    elif "linkedin.com" in href:
        suggestions.append({
            "name": "linkedin_url",
            "confidence": 0.95,
            "attribute": "href",
            "reason": "LinkedIn URL"
        })
    elif "twitter.com" in href or "x.com" in href:
        suggestions.append({
            "name": "twitter_url",
            "confidence": 0.95,
            "attribute": "href",
            "reason": "Twitter/X URL"
        })
    elif "facebook.com" in href:
        suggestions.append({
            "name": "facebook_url",
            "confidence": 0.95,
            "attribute": "href",
            "reason": "Facebook URL"
        })

    # Check for full address pattern FIRST (before checking other patterns)
    # This ensures "12472 Memorial Dr, Houston, TX, 77024" is detected as address, not zip
    address_patterns = [
        (r'^\d+\s+[\w\s]+(ST|AVE|BLVD|RD|DR|LN|CT|WAY|PL|STREET|AVENUE|ROAD|DRIVE|LANE)\b', "starts with street number"),
        (r'\d+\s+\w+.*,\s*[A-Z]{2}\s*\d{5}', "full address with city/state/zip"),
        (r',\s*[A-Z][a-z]+,\s*[A-Z]{2}\s*\d{5}', "city, state ZIP pattern"),
    ]
    for pattern, reason in address_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            suggestions.append({
                "name": "address",
                "confidence": 0.92,
                "attribute": None,
                "reason": f"content matches address pattern ({reason})"
            })
            break  # Only add once

    # Check class names and IDs for hints
    for field_name, pattern_info in FIELD_PATTERNS.items():
        confidence = 0.0
        reason = ""
        attribute = pattern_info.get("attribute")

        # Check class names
        for selector in pattern_info.get("selectors", []):
            # Extract class name from selector like '.email' or '[data-email]'
            if selector.startswith("."):
                class_hint = selector[1:].lower()
                if class_hint in classes_str:
                    confidence = max(confidence, 0.85)
                    reason = f"class contains '{class_hint}'"
            elif selector.startswith("[data-"):
                # Data attribute hint
                data_attr = selector[6:-1].lower()
                if data_attr in classes_str or data_attr in element_id:
                    confidence = max(confidence, 0.80)
                    reason = f"data attribute '{data_attr}'"

        # Check context hints in parent/nearby text
        for hint in pattern_info.get("context_hints", []):
            if hint in parent_classes_str or hint in element_id:
                confidence = max(confidence, 0.70)
                reason = f"context: '{hint}'"

        # Check content patterns (skip zip if we already detected address)
        if field_name == "zip" and any(s["name"] == "address" for s in suggestions):
            continue  # Skip zip detection if address already detected

        for pattern in pattern_info.get("content_patterns", []):
            if re.search(pattern, text, re.IGNORECASE):
                # Use priority to set confidence
                priority = pattern_info.get("priority", 50)
                conf = 0.5 + (priority / 200)  # Higher priority = higher confidence
                confidence = max(confidence, conf)
                reason = f"content matches {field_name} pattern"

        # Check tag-based hints
        if tag == "h1" and field_name in ["company_name", "person_name"]:
            confidence = max(confidence, 0.60)
            reason = "main heading (h1)"
        elif tag == "address" and field_name == "address":
            confidence = max(confidence, 0.90)
            reason = "semantic <address> tag"
        elif tag == "img" and field_name in ["logo", "avatar", "image"]:
            confidence = max(confidence, 0.70)
            reason = "image element"
            attribute = "src"

        if confidence > 0.5:
            suggestions.append({
                "name": field_name,
                "confidence": confidence,
                "attribute": attribute,
                "reason": reason
            })

    # Sort by confidence (highest first)
    suggestions.sort(key=lambda x: x["confidence"], reverse=True)

    # Add generic fallback if no good suggestions
    if not suggestions or suggestions[0]["confidence"] < 0.6:
        if tag == "a" and href:
            suggestions.append({
                "name": "link",
                "confidence": 0.4,
                "attribute": "href",
                "reason": "generic link"
            })
        elif tag == "img":
            suggestions.append({
                "name": "image",
                "confidence": 0.4,
                "attribute": "src",
                "reason": "image element"
            })
        elif tag in ["h1", "h2", "h3"]:
            suggestions.append({
                "name": "title",
                "confidence": 0.5,
                "reason": f"heading ({tag})"
            })
        else:
            suggestions.append({
                "name": "field",
                "confidence": 0.3,
                "reason": "generic field"
            })

    return suggestions[:5]  # Return top 5 suggestions


def get_auto_detect_js() -> str:
    """
    Return JavaScript code for auto-detecting common fields on a page.

    Returns JS that when executed returns an array of detected fields.
    """
    return """
    (function() {
        var detected = [];

        // Email links
        var emails = document.querySelectorAll('a[href^="mailto:"]');
        if (emails.length > 0) {
            detected.push({
                name: 'email',
                selector: 'a[href^="mailto:"]',
                count: emails.length,
                sample: emails[0].getAttribute('href').replace('mailto:', '').split('?')[0],
                attribute: 'href'
            });
        }

        // Phone links
        var phones = document.querySelectorAll('a[href^="tel:"]');
        if (phones.length > 0) {
            detected.push({
                name: 'phone',
                selector: 'a[href^="tel:"]',
                count: phones.length,
                sample: phones[0].getAttribute('href').replace('tel:', '').replace(/[^0-9+()-]/g, ''),
                attribute: 'href'
            });
        }

        // LinkedIn links
        var linkedin = document.querySelectorAll('a[href*="linkedin.com"]');
        if (linkedin.length > 0) {
            detected.push({
                name: 'linkedin_url',
                selector: 'a[href*="linkedin.com"]',
                count: linkedin.length,
                sample: linkedin[0].getAttribute('href'),
                attribute: 'href'
            });
        }

        // Twitter/X links
        var twitter = document.querySelectorAll('a[href*="twitter.com"], a[href*="x.com"]');
        if (twitter.length > 0) {
            detected.push({
                name: 'twitter_url',
                selector: 'a[href*="twitter.com"], a[href*="x.com"]',
                count: twitter.length,
                sample: twitter[0].getAttribute('href'),
                attribute: 'href'
            });
        }

        // Facebook links
        var facebook = document.querySelectorAll('a[href*="facebook.com"]');
        if (facebook.length > 0) {
            detected.push({
                name: 'facebook_url',
                selector: 'a[href*="facebook.com"]',
                count: facebook.length,
                sample: facebook[0].getAttribute('href'),
                attribute: 'href'
            });
        }

        // Address elements - try semantic markup first
        var addresses = document.querySelectorAll('address, .address, [data-address], .location, [itemprop="address"], .street-address');
        if (addresses.length > 0) {
            detected.push({
                name: 'address',
                selector: 'address, .address, [data-address], .location',
                count: addresses.length,
                sample: addresses[0].textContent.trim().substring(0, 100),
                attribute: null
            });
        } else {
            // If no semantic address found, look for text matching address patterns
            // Common patterns: "123 Main St", "City, ST 12345"
            var addressPattern = /\d+\s+[\w\s]+(ST|AVE|BLVD|RD|DR|LN|CT|WAY|PL|STREET|AVENUE|ROAD|DRIVE|HIGHWAY|HWY)\b/i;
            var zipPattern = /,\s*[A-Z]{2},?\s*\d{5}/i;

            // Search in common contact containers
            var contactContainers = document.querySelectorAll('.contact, .contact-info, .business-info, .company-info, .details, .info-section, [class*="contact"], [class*="address"], [class*="location"]');

            for (var i = 0; i < contactContainers.length; i++) {
                var container = contactContainers[i];
                var text = container.textContent || '';

                if (addressPattern.test(text) || zipPattern.test(text)) {
                    // Found address-like text - try to find the specific element
                    var children = container.querySelectorAll('p, div, span, li');
                    for (var j = 0; j < children.length; j++) {
                        var childText = children[j].textContent.trim();
                        if ((addressPattern.test(childText) || zipPattern.test(childText)) && childText.length > 10 && childText.length < 200) {
                            // Build a selector for this element
                            var el = children[j];
                            var selector = el.tagName.toLowerCase();
                            if (el.className) {
                                var classes = el.className.split(/\s+/).filter(function(c) { return c && c.length < 30; });
                                if (classes.length > 0) selector += '.' + classes[0];
                            }
                            detected.push({
                                name: 'address',
                                selector: selector,
                                count: 1,
                                sample: childText.substring(0, 100),
                                attribute: null
                            });
                            break;
                        }
                    }
                    if (detected.some(function(d) { return d.name === 'address'; })) break;
                }
            }

            // Last resort: look near phone/email elements
            if (!detected.some(function(d) { return d.name === 'address'; })) {
                var phoneEmail = document.querySelectorAll('a[href^="tel:"], a[href^="mailto:"]');
                for (var k = 0; k < phoneEmail.length; k++) {
                    var parent = phoneEmail[k].parentElement;
                    if (parent) {
                        // Check siblings
                        var siblings = parent.children;
                        for (var m = 0; m < siblings.length; m++) {
                            var sibText = siblings[m].textContent.trim();
                            if ((addressPattern.test(sibText) || zipPattern.test(sibText)) && sibText.length > 10 && sibText.length < 200) {
                                var sibEl = siblings[m];
                                var sibSelector = sibEl.tagName.toLowerCase();
                                if (sibEl.className) {
                                    var sibClasses = sibEl.className.split(/\s+/).filter(function(c) { return c && c.length < 30; });
                                    if (sibClasses.length > 0) sibSelector += '.' + sibClasses[0];
                                }
                                detected.push({
                                    name: 'address',
                                    selector: sibSelector,
                                    count: 1,
                                    sample: sibText.substring(0, 100),
                                    attribute: null
                                });
                                break;
                            }
                        }
                    }
                    if (detected.some(function(d) { return d.name === 'address'; })) break;
                }
            }
        }

        // External website links (excluding social media)
        var websites = document.querySelectorAll('a[rel="external"], a.website, a.external-link');
        if (websites.length > 0) {
            var validWebsites = Array.from(websites).filter(function(a) {
                var href = a.getAttribute('href') || '';
                return href.startsWith('http') &&
                       !href.includes('linkedin.com') &&
                       !href.includes('twitter.com') &&
                       !href.includes('facebook.com') &&
                       !href.includes('instagram.com');
            });
            if (validWebsites.length > 0) {
                detected.push({
                    name: 'website',
                    selector: 'a[rel="external"], a.website',
                    count: validWebsites.length,
                    sample: validWebsites[0].getAttribute('href'),
                    attribute: 'href'
                });
            }
        }

        return detected;
    })();
    """


# Business field presets for quick setup
BUSINESS_FIELD_PRESETS = {
    "contact_basic": [
        {"name": "email", "selector": 'a[href^="mailto:"]', "attribute": "href"},
        {"name": "phone", "selector": 'a[href^="tel:"]', "attribute": "href"},
        {"name": "address", "selector": ".address, address, [data-address], .location, [itemprop='address'], .street-address"},
    ],
    "company_info": [
        {"name": "company_name", "selector": "h1, .company-name, [data-company]"},
        {"name": "description", "selector": ".description, .about, .summary"},
        {"name": "industry", "selector": ".industry, [data-industry], .sector"},
        {"name": "employees", "selector": ".employees, .company-size"},
    ],
    "social_links": [
        {"name": "linkedin_url", "selector": 'a[href*="linkedin.com"]', "attribute": "href"},
        {"name": "twitter_url", "selector": 'a[href*="twitter.com"]', "attribute": "href"},
        {"name": "facebook_url", "selector": 'a[href*="facebook.com"]', "attribute": "href"},
    ],
}
