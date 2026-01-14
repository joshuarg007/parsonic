"""Diff detection for comparing scrape results between runs."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class DiffStatus(str, Enum):
    NEW = "new"
    CHANGED = "changed"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


@dataclass
class DiffResult:
    """Result of comparing a single record."""
    key: str  # Unique identifier for the record
    status: DiffStatus
    current_data: Optional[dict] = None
    previous_data: Optional[dict] = None
    changed_fields: list[str] = field(default_factory=list)


@dataclass
class DiffSummary:
    """Summary of all differences between runs."""
    timestamp: datetime
    total_current: int
    total_previous: int
    new_count: int
    changed_count: int
    removed_count: int
    unchanged_count: int
    results: list[DiffResult] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return self.new_count > 0 or self.changed_count > 0 or self.removed_count > 0


class DiffDetector:
    """Detects differences between scrape runs."""

    def __init__(self, storage_dir: str = "data/history"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_history_path(self, project_name: str) -> Path:
        """Get path to history file for a project."""
        safe_name = "".join(c if c.isalnum() else "_" for c in project_name)
        return self.storage_dir / f"{safe_name}_history.json"

    def _compute_record_hash(self, data: dict) -> str:
        """Compute hash of a record for comparison."""
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(content.encode()).hexdigest()

    def _get_record_key(self, data: dict, key_fields: list[str] = None) -> str:
        """Get unique key for a record."""
        if key_fields:
            key_parts = [str(data.get(f, "")) for f in key_fields]
            return "|".join(key_parts)
        else:
            # Use hash of entire record as key
            return self._compute_record_hash(data)

    def save_results(
        self,
        project_name: str,
        results: list[dict],
        key_fields: list[str] = None
    ):
        """Save current results for future comparison."""
        history_path = self._get_history_path(project_name)

        # Load existing history
        history = self._load_history(history_path)

        # Add current run
        run_data = {
            "timestamp": datetime.now().isoformat(),
            "records": {}
        }

        for record in results:
            key = self._get_record_key(record, key_fields)
            run_data["records"][key] = {
                "data": record,
                "hash": self._compute_record_hash(record)
            }

        # Keep last 10 runs
        history["runs"] = history.get("runs", [])[-9:] + [run_data]
        history["last_updated"] = datetime.now().isoformat()

        # Save
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2, default=str)

    def _load_history(self, path: Path) -> dict:
        """Load history from file."""
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"runs": []}

    def compare(
        self,
        project_name: str,
        current_results: list[dict],
        key_fields: list[str] = None
    ) -> DiffSummary:
        """Compare current results with previous run."""
        history_path = self._get_history_path(project_name)
        history = self._load_history(history_path)

        # Get previous run
        runs = history.get("runs", [])
        previous_records = {}
        if runs:
            last_run = runs[-1]
            previous_records = last_run.get("records", {})

        # Build current records map
        current_records = {}
        for record in current_results:
            key = self._get_record_key(record, key_fields)
            current_records[key] = {
                "data": record,
                "hash": self._compute_record_hash(record)
            }

        # Compare
        diff_results = []
        new_count = 0
        changed_count = 0
        unchanged_count = 0

        # Check current records
        for key, current in current_records.items():
            if key not in previous_records:
                # New record
                diff_results.append(DiffResult(
                    key=key,
                    status=DiffStatus.NEW,
                    current_data=current["data"]
                ))
                new_count += 1
            else:
                previous = previous_records[key]
                if current["hash"] != previous["hash"]:
                    # Changed record
                    changed_fields = self._find_changed_fields(
                        previous["data"],
                        current["data"]
                    )
                    diff_results.append(DiffResult(
                        key=key,
                        status=DiffStatus.CHANGED,
                        current_data=current["data"],
                        previous_data=previous["data"],
                        changed_fields=changed_fields
                    ))
                    changed_count += 1
                else:
                    # Unchanged
                    diff_results.append(DiffResult(
                        key=key,
                        status=DiffStatus.UNCHANGED,
                        current_data=current["data"]
                    ))
                    unchanged_count += 1

        # Check for removed records
        removed_count = 0
        for key, previous in previous_records.items():
            if key not in current_records:
                diff_results.append(DiffResult(
                    key=key,
                    status=DiffStatus.REMOVED,
                    previous_data=previous["data"]
                ))
                removed_count += 1

        return DiffSummary(
            timestamp=datetime.now(),
            total_current=len(current_records),
            total_previous=len(previous_records),
            new_count=new_count,
            changed_count=changed_count,
            removed_count=removed_count,
            unchanged_count=unchanged_count,
            results=diff_results
        )

    def _find_changed_fields(self, old: dict, new: dict) -> list[str]:
        """Find which fields changed between two records."""
        changed = []
        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)

            if old_val != new_val:
                changed.append(key)

        return changed

    def get_history(self, project_name: str) -> list[dict]:
        """Get run history for a project."""
        history_path = self._get_history_path(project_name)
        history = self._load_history(history_path)

        runs = []
        for run in history.get("runs", []):
            runs.append({
                "timestamp": run.get("timestamp"),
                "record_count": len(run.get("records", {}))
            })

        return runs

    def clear_history(self, project_name: str):
        """Clear history for a project."""
        history_path = self._get_history_path(project_name)
        if history_path.exists():
            history_path.unlink()
