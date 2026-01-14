"""Core functionality for Parsonic."""

from src.core.scraper import ScraperOrchestrator
from src.core.scheduler import ScraperScheduler
from src.core.proxy_manager import ProxyManager
from src.core.diff_detector import DiffDetector, DiffStatus, DiffSummary
from src.core.transforms import TransformPipeline, create_pipeline_from_config
from src.core.templates import TEMPLATES, get_template, list_templates
from src.core.exporter import ExporterFactory, CSVExporter, JSONExporter, SQLiteExporter

__all__ = [
    'ScraperOrchestrator',
    'ScraperScheduler',
    'ProxyManager',
    'DiffDetector',
    'DiffStatus',
    'DiffSummary',
    'TransformPipeline',
    'create_pipeline_from_config',
    'TEMPLATES',
    'get_template',
    'list_templates',
    'ExporterFactory',
    'CSVExporter',
    'JSONExporter',
    'SQLiteExporter',
]
