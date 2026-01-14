"""Data exporters for Parsonic (CSV, JSON, SQLite)."""

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    path: str
    record_count: int
    error: Optional[str] = None


class CSVExporter:
    """Export data to CSV format."""

    def export(self, data: list[dict], path: str, fields: list[str] = None) -> ExportResult:
        """Export data to CSV file."""
        try:
            if not data:
                return ExportResult(False, path, 0, "No data to export")

            # Determine fields
            if fields is None:
                fields = list(data[0].keys())

            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(data)

            return ExportResult(True, path, len(data))

        except Exception as e:
            return ExportResult(False, path, 0, str(e))


class JSONExporter:
    """Export data to JSON format."""

    def export(
        self,
        data: list[dict],
        path: str,
        indent: int = 2,
        include_metadata: bool = True
    ) -> ExportResult:
        """Export data to JSON file."""
        try:
            if not data:
                return ExportResult(False, path, 0, "No data to export")

            output = data
            if include_metadata:
                output = {
                    "metadata": {
                        "exported_at": datetime.now().isoformat(),
                        "record_count": len(data),
                        "fields": list(data[0].keys()) if data else []
                    },
                    "data": data
                }

            with open(path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=indent, ensure_ascii=False, default=str)

            return ExportResult(True, path, len(data))

        except Exception as e:
            return ExportResult(False, path, 0, str(e))


class SQLiteExporter:
    """Export data to SQLite database."""

    def _sanitize_identifier(self, name: str) -> str:
        """Sanitize a SQL identifier (table/column name) to prevent injection."""
        # Only allow alphanumeric and underscore
        return "".join(c if c.isalnum() or c == "_" else "_" for c in name)

    def export(
        self,
        data: list[dict],
        path: str,
        table_name: str = "scraped_data",
        if_exists: str = "replace"  # replace, append, fail
    ) -> ExportResult:
        """Export data to SQLite database."""
        try:
            if not data:
                return ExportResult(False, path, 0, "No data to export")

            # Sanitize table name to prevent SQL injection
            table_name = self._sanitize_identifier(table_name)

            # Determine schema from data
            fields = list(data[0].keys())
            field_types = self._infer_types(data[0])

            conn = sqlite3.connect(path)
            cursor = conn.cursor()

            # Handle existing table
            if if_exists == "replace":
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            elif if_exists == "fail":
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if cursor.fetchone():
                    return ExportResult(False, path, 0, f"Table {table_name} already exists")

            # Create table
            if if_exists != "append":
                columns = ", ".join(
                    f'"{self._sanitize_identifier(f)}" {field_types.get(f, "TEXT")}' for f in fields
                )
                cursor.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({columns})')

            # Insert data
            placeholders = ", ".join("?" for _ in fields)
            column_names = ", ".join(f'"{self._sanitize_identifier(f)}"' for f in fields)
            insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'

            for record in data:
                values = [record.get(f) for f in fields]
                cursor.execute(insert_sql, values)

            # Add metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS _parsonic_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.execute(
                "INSERT OR REPLACE INTO _parsonic_metadata VALUES (?, ?)",
                ("last_export", datetime.now().isoformat())
            )
            cursor.execute(
                "INSERT OR REPLACE INTO _parsonic_metadata VALUES (?, ?)",
                ("record_count", str(len(data)))
            )

            conn.commit()
            conn.close()

            return ExportResult(True, path, len(data))

        except Exception as e:
            return ExportResult(False, path, 0, str(e))

    def _infer_types(self, record: dict) -> dict[str, str]:
        """Infer SQLite types from a sample record."""
        types = {}
        for key, value in record.items():
            if value is None:
                types[key] = "TEXT"
            elif isinstance(value, bool):
                types[key] = "INTEGER"
            elif isinstance(value, int):
                types[key] = "INTEGER"
            elif isinstance(value, float):
                types[key] = "REAL"
            else:
                types[key] = "TEXT"
        return types


class ExporterFactory:
    """Factory for creating exporters."""

    @staticmethod
    def create(format: str):
        """Create an exporter for the given format."""
        exporters = {
            "csv": CSVExporter,
            "json": JSONExporter,
            "sqlite": SQLiteExporter,
        }
        if format.lower() in exporters:
            return exporters[format.lower()]()
        raise ValueError(f"Unknown export format: {format}")

    @staticmethod
    def export(data: list[dict], path: str, format: str = None, **kwargs) -> ExportResult:
        """Export data to file, auto-detecting format from extension."""
        if format is None:
            ext = Path(path).suffix.lower()
            format_map = {
                ".csv": "csv",
                ".json": "json",
                ".db": "sqlite",
                ".sqlite": "sqlite",
                ".sqlite3": "sqlite",
            }
            format = format_map.get(ext, "json")

        exporter = ExporterFactory.create(format)
        return exporter.export(data, path, **kwargs)
