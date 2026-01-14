"""Data transformation pipeline for Parsonic."""

import re
import html
from typing import Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class TransformResult:
    """Result of a transformation."""
    success: bool
    value: Any
    error: Optional[str] = None


class Transform:
    """Base class for data transformations."""

    name: str = "base"
    description: str = ""

    def apply(self, value: Any) -> TransformResult:
        """Apply the transformation."""
        raise NotImplementedError


class TrimTransform(Transform):
    """Remove leading/trailing whitespace."""

    name = "trim"
    description = "Remove leading and trailing whitespace"

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            return TransformResult(True, str(value).strip())
        except Exception as e:
            return TransformResult(False, value, str(e))


class LowerTransform(Transform):
    """Convert to lowercase."""

    name = "lowercase"
    description = "Convert text to lowercase"

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            return TransformResult(True, str(value).lower())
        except Exception as e:
            return TransformResult(False, value, str(e))


class UpperTransform(Transform):
    """Convert to uppercase."""

    name = "uppercase"
    description = "Convert text to uppercase"

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            return TransformResult(True, str(value).upper())
        except Exception as e:
            return TransformResult(False, value, str(e))


class StripHtmlTransform(Transform):
    """Remove HTML tags."""

    name = "strip_html"
    description = "Remove HTML tags from text"

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            # Remove HTML tags
            clean = re.sub(r'<[^>]+>', '', str(value))
            # Decode HTML entities
            clean = html.unescape(clean)
            # Clean up whitespace
            clean = re.sub(r'\s+', ' ', clean).strip()
            return TransformResult(True, clean)
        except Exception as e:
            return TransformResult(False, value, str(e))


class RegexExtractTransform(Transform):
    """Extract text using regex."""

    name = "regex_extract"
    description = "Extract text matching a regular expression"

    def __init__(self, pattern: str, group: int = 0):
        self.pattern = pattern
        self.group = group

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            match = re.search(self.pattern, str(value))
            if match:
                return TransformResult(True, match.group(self.group))
            return TransformResult(True, None)
        except Exception as e:
            return TransformResult(False, value, str(e))


class RegexReplaceTransform(Transform):
    """Replace text using regex."""

    name = "regex_replace"
    description = "Replace text matching a pattern"

    def __init__(self, pattern: str, replacement: str):
        self.pattern = pattern
        self.replacement = replacement

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            result = re.sub(self.pattern, self.replacement, str(value))
            return TransformResult(True, result)
        except Exception as e:
            return TransformResult(False, value, str(e))


class SplitTransform(Transform):
    """Split text and get a specific part."""

    name = "split"
    description = "Split text by delimiter and get specific part"

    def __init__(self, delimiter: str, index: int = 0):
        self.delimiter = delimiter
        self.index = index

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            parts = str(value).split(self.delimiter)
            if 0 <= self.index < len(parts):
                return TransformResult(True, parts[self.index].strip())
            elif self.index < 0 and abs(self.index) <= len(parts):
                return TransformResult(True, parts[self.index].strip())
            return TransformResult(True, None)
        except Exception as e:
            return TransformResult(False, value, str(e))


class NumberTransform(Transform):
    """Extract and convert to number."""

    name = "to_number"
    description = "Extract numeric value from text"

    def __init__(self, decimal_sep: str = ".", thousands_sep: str = ","):
        self.decimal_sep = decimal_sep
        self.thousands_sep = thousands_sep

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            # Remove currency symbols and whitespace
            clean = re.sub(r'[^\d.,\-]', '', str(value))

            # Handle thousands separator
            if self.thousands_sep:
                clean = clean.replace(self.thousands_sep, '')

            # Handle decimal separator
            if self.decimal_sep != '.':
                clean = clean.replace(self.decimal_sep, '.')

            # Try to convert
            if '.' in clean:
                return TransformResult(True, float(clean))
            else:
                return TransformResult(True, int(clean))
        except Exception as e:
            return TransformResult(False, value, str(e))


class DateTransform(Transform):
    """Parse and format dates."""

    name = "date"
    description = "Parse date and optionally reformat"

    def __init__(self, input_format: str = None, output_format: str = "%Y-%m-%d"):
        self.input_format = input_format
        self.output_format = output_format

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            from datetime import datetime
            from dateutil import parser

            if self.input_format:
                dt = datetime.strptime(str(value), self.input_format)
            else:
                dt = parser.parse(str(value))

            return TransformResult(True, dt.strftime(self.output_format))
        except Exception as e:
            return TransformResult(False, value, str(e))


class UrlTransform(Transform):
    """Extract or validate URLs."""

    name = "url"
    description = "Extract or normalize URLs"

    def __init__(self, base_url: str = None):
        self.base_url = base_url

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            from urllib.parse import urljoin, urlparse

            url = str(value).strip()

            # Make absolute if base URL provided
            if self.base_url and not url.startswith(('http://', 'https://')):
                url = urljoin(self.base_url, url)

            # Validate URL
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:
                return TransformResult(True, url)

            return TransformResult(False, value, "Invalid URL")
        except Exception as e:
            return TransformResult(False, value, str(e))


class DefaultTransform(Transform):
    """Provide default value if empty."""

    name = "default"
    description = "Use default value if empty"

    def __init__(self, default_value: Any):
        self.default_value = default_value

    def apply(self, value: Any) -> TransformResult:
        if value is None or (isinstance(value, str) and not value.strip()):
            return TransformResult(True, self.default_value)
        return TransformResult(True, value)


class CustomTransform(Transform):
    """Custom Python expression transform."""

    name = "custom"
    description = "Apply custom Python expression"

    def __init__(self, expression: str):
        self.expression = expression

    def apply(self, value: Any) -> TransformResult:
        if value is None:
            return TransformResult(True, None)
        try:
            # Create safe namespace
            namespace = {
                "value": value,
                "str": str,
                "int": int,
                "float": float,
                "len": len,
                "re": re,
                "html": html,
            }
            result = eval(self.expression, {"__builtins__": {}}, namespace)
            return TransformResult(True, result)
        except Exception as e:
            return TransformResult(False, value, str(e))


class TransformPipeline:
    """Pipeline of transforms to apply in sequence."""

    def __init__(self, transforms: list[Transform] = None):
        self.transforms = transforms or []

    def add(self, transform: Transform) -> "TransformPipeline":
        """Add a transform to the pipeline."""
        self.transforms.append(transform)
        return self

    def apply(self, value: Any) -> TransformResult:
        """Apply all transforms in sequence."""
        current = value

        for transform in self.transforms:
            result = transform.apply(current)
            if not result.success:
                return result
            current = result.value

        return TransformResult(True, current)

    def apply_to_record(self, record: dict, field_pipelines: dict[str, "TransformPipeline"]) -> dict:
        """Apply field-specific pipelines to a record."""
        result = record.copy()

        for field, pipeline in field_pipelines.items():
            if field in result:
                transform_result = pipeline.apply(result[field])
                if transform_result.success:
                    result[field] = transform_result.value

        return result


# Built-in transform registry
TRANSFORMS = {
    "trim": TrimTransform,
    "lowercase": LowerTransform,
    "uppercase": UpperTransform,
    "strip_html": StripHtmlTransform,
    "to_number": NumberTransform,
    "date": DateTransform,
    "url": UrlTransform,
}


def create_pipeline_from_config(config: list[dict]) -> TransformPipeline:
    """Create a transform pipeline from configuration."""
    pipeline = TransformPipeline()

    for item in config:
        transform_type = item.get("type")
        params = item.get("params", {})

        if transform_type == "regex_extract":
            pipeline.add(RegexExtractTransform(
                pattern=params.get("pattern", ""),
                group=params.get("group", 0)
            ))
        elif transform_type == "regex_replace":
            pipeline.add(RegexReplaceTransform(
                pattern=params.get("pattern", ""),
                replacement=params.get("replacement", "")
            ))
        elif transform_type == "split":
            pipeline.add(SplitTransform(
                delimiter=params.get("delimiter", " "),
                index=params.get("index", 0)
            ))
        elif transform_type == "default":
            pipeline.add(DefaultTransform(params.get("value", "")))
        elif transform_type == "custom":
            pipeline.add(CustomTransform(params.get("expression", "value")))
        elif transform_type in TRANSFORMS:
            pipeline.add(TRANSFORMS[transform_type](**params))

    return pipeline
