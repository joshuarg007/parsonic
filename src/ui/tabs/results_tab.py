"""Results viewer tab for Parsonic."""

import json
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QLineEdit, QHeaderView, QMenu,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from src.models.project import ScraperProject


class ResultsTab(QWidget):
    """Tab for viewing and exporting scraped results."""

    # Default results storage path
    RESULTS_DIR = Path.home() / ".parsonic"
    RESULTS_FILE = RESULTS_DIR / "results.json"

    def __init__(self, project: ScraperProject):
        super().__init__()
        self.project = project
        self._results = []
        self._columns = []  # Track column names for persistence
        self._setup_ui()
        self._load_results()  # Load previous results on startup

    def _setup_ui(self):
        """Build the results viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()

        # Filter
        toolbar.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Search results...")
        self.filter_input.textChanged.connect(self._filter_results)
        self.filter_input.setMaximumWidth(250)
        toolbar.addWidget(self.filter_input)

        # Column filter
        toolbar.addWidget(QLabel("Column:"))
        self.column_combo = QComboBox()
        self.column_combo.addItem("All columns")
        self.column_combo.currentIndexChanged.connect(self._filter_results)
        toolbar.addWidget(self.column_combo)

        toolbar.addStretch()

        # Stats
        self.stats_label = QLabel("0 results")
        toolbar.addWidget(self.stats_label)

        # Export buttons
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.setProperty("secondary", True)
        self.export_csv_btn.clicked.connect(lambda: self._export("csv"))
        toolbar.addWidget(self.export_csv_btn)

        self.export_json_btn = QPushButton("Export JSON")
        self.export_json_btn.setProperty("secondary", True)
        self.export_json_btn.clicked.connect(lambda: self._export("json"))
        toolbar.addWidget(self.export_json_btn)

        # Clear button
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setProperty("secondary", True)
        self.clear_btn.setToolTip("Clear all results (cannot be undone)")
        self.clear_btn.clicked.connect(self._confirm_clear)
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # Results table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

        # Diff legend
        diff_layout = QHBoxLayout()
        diff_layout.addWidget(QLabel("Changes:"))

        new_label = QLabel("New")
        new_label.setStyleSheet("background-color: #2d4a2d; padding: 2px 8px; border-radius: 3px;")
        diff_layout.addWidget(new_label)

        changed_label = QLabel("Changed")
        changed_label.setStyleSheet("background-color: #4a4a2d; padding: 2px 8px; border-radius: 3px;")
        diff_layout.addWidget(changed_label)

        removed_label = QLabel("Removed")
        removed_label.setStyleSheet("background-color: #4a2d2d; padding: 2px 8px; border-radius: 3px;")
        diff_layout.addWidget(removed_label)

        diff_layout.addStretch()

        self.duplicates_label = QLabel("0 duplicates hidden")
        self.duplicates_label.setStyleSheet("color: #969696;")
        diff_layout.addWidget(self.duplicates_label)

        layout.addLayout(diff_layout)

    def set_columns(self, columns: list[str]):
        """Set the table columns based on field definitions."""
        self._columns = columns  # Track for persistence
        self.table.setColumnCount(len(columns) + 1)  # +1 for source URL
        self.table.setHorizontalHeaderLabels(["Source URL"] + columns)

        # Update column filter
        self.column_combo.clear()
        self.column_combo.addItem("All columns")
        for col in columns:
            self.column_combo.addItem(col)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        for i in range(1, len(columns) + 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

    def add_result(self, source_url: str, data: dict, diff_status: str = None):
        """Add a result row to the table."""
        # Validate: must have at least one essential business field
        essential_fields = ['company_name', 'email', 'phone', 'address']
        has_essential = False
        for field in essential_fields:
            value = data.get(field)
            if value and str(value).strip() and str(value).strip().lower() not in ['none', 'n/a', 'null', '']:
                has_essential = True
                break

        if not has_essential:
            # Skip invalid entries - no business data found
            print(f"Skipping invalid result (no essential fields): {source_url}")
            return

        # Skip duplicates (same source URL)
        for existing in self._results:
            if existing.get("source") == source_url:
                # Update existing entry if data changed
                if existing.get("data") != data:
                    existing["data"] = data
                    existing["status"] = "changed"
                    self._refresh_table()
                    self._save_results()
                return

        row = self.table.rowCount()
        self.table.insertRow(row)

        # Source URL
        url_item = QTableWidgetItem(source_url)
        self.table.setItem(row, 0, url_item)

        # Data columns
        for col, (key, value) in enumerate(data.items(), start=1):
            item = QTableWidgetItem(str(value) if value else "")
            self.table.setItem(row, col, item)

        # Apply diff highlighting
        if diff_status:
            color = {
                "new": "#2d4a2d",
                "changed": "#4a4a2d",
                "removed": "#4a2d2d"
            }.get(diff_status)

            if color:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(Qt.GlobalColor.transparent)
                        item.setData(Qt.ItemDataRole.BackgroundRole, color)

        self._results.append({"source": source_url, "data": data, "status": diff_status})
        self._save_results()  # Auto-save after each result
        self._update_stats()

    def set_results(self, results: list[dict]):
        """Replace all results with new data."""
        self.clear()
        for result in results:
            self.add_result(
                result.get("source", ""),
                result.get("data", {}),
                result.get("status")
            )

    def clear(self):
        """Clear all results."""
        self.table.setRowCount(0)
        self._results.clear()
        self._update_stats()

    def _update_stats(self):
        """Update the stats label."""
        total = len(self._results)
        filtered = self.table.rowCount()

        if total == filtered:
            self.stats_label.setText(f"{total} results")
        else:
            self.stats_label.setText(f"{filtered} of {total} results")

    def _filter_results(self):
        """Filter visible results based on search text."""
        search = self.filter_input.text().lower()
        column = self.column_combo.currentIndex() - 1  # -1 for "All columns"

        for row in range(self.table.rowCount()):
            visible = False

            if column < 0:  # All columns
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item and search in item.text().lower():
                        visible = True
                        break
            else:
                item = self.table.item(row, column + 1)  # +1 for source URL column
                if item and search in item.text().lower():
                    visible = True

            self.table.setRowHidden(row, not visible)

        self._update_stats()

    def _show_context_menu(self, pos):
        """Show right-click context menu."""
        menu = QMenu(self)

        copy_action = QAction("Copy Cell", self)
        copy_action.triggered.connect(self._copy_cell)
        menu.addAction(copy_action)

        copy_row_action = QAction("Copy Row", self)
        copy_row_action.triggered.connect(self._copy_row)
        menu.addAction(copy_row_action)

        menu.addSeparator()

        open_url_action = QAction("Open Source URL", self)
        open_url_action.triggered.connect(self._open_source_url)
        menu.addAction(open_url_action)

        rescrape_action = QAction("Re-scrape This URL", self)
        rescrape_action.triggered.connect(self._rescrape_url)
        menu.addAction(rescrape_action)

        menu.addSeparator()

        exclude_action = QAction("Exclude Row", self)
        exclude_action.triggered.connect(self._exclude_row)
        menu.addAction(exclude_action)

        menu.exec(self.table.mapToGlobal(pos))

    def _copy_cell(self):
        """Copy selected cell to clipboard."""
        from PyQt6.QtWidgets import QApplication

        item = self.table.currentItem()
        if item:
            QApplication.clipboard().setText(item.text())

    def _copy_row(self):
        """Copy selected row to clipboard."""
        from PyQt6.QtWidgets import QApplication

        row = self.table.currentRow()
        if row >= 0:
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append(item.text() if item else "")
            QApplication.clipboard().setText("\t".join(values))

    def _open_source_url(self):
        """Open source URL in browser."""
        import webbrowser

        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                webbrowser.open(item.text())

    def _rescrape_url(self):
        """Re-scrape the selected URL."""
        # TODO: Implement re-scrape
        pass

    def _exclude_row(self):
        """Exclude selected row from results."""
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            if row < len(self._results):
                self._results.pop(row)
            self._update_stats()

    def _export(self, format: str):
        """Export results to file."""
        if not self._results:
            QMessageBox.warning(self, "No Data", "No results to export.")
            return

        ext = {"csv": "CSV Files (*.csv)", "json": "JSON Files (*.json)"}
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export to {format.upper()}",
            f"results.{format}",
            ext.get(format, "All Files (*)")
        )

        if path:
            try:
                if format == "csv":
                    self._export_csv(path)
                elif format == "json":
                    self._export_json(path)
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    def _export_csv(self, path: str):
        """Export results to CSV."""
        import csv

        with open(path, 'w', newline='', encoding='utf-8') as f:
            if self._results:
                # Get column headers
                headers = ["source"] + list(self._results[0].get("data", {}).keys())
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

                for result in self._results:
                    row = {"source": result.get("source", "")}
                    row.update(result.get("data", {}))
                    writer.writerow(row)

    def _export_json(self, path: str):
        """Export results to JSON."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self._results, f, indent=2, ensure_ascii=False)

    def _save_results(self):
        """Save results to persistent storage."""
        try:
            # Ensure directory exists
            self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

            # Save results and columns
            data = {
                "columns": self._columns,
                "results": self._results
            }

            with open(self.RESULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save results: {e}")

    def _load_results(self):
        """Load results from persistent storage."""
        if not self.RESULTS_FILE.exists():
            return

        try:
            with open(self.RESULTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Restore columns
            columns = data.get("columns", [])
            if columns:
                self.set_columns(columns)

            # Restore results
            results = data.get("results", [])
            for result in results:
                source = result.get("source", "")
                result_data = result.get("data", {})
                status = result.get("status")

                # Add to table (without triggering save again)
                row = self.table.rowCount()
                self.table.insertRow(row)

                url_item = QTableWidgetItem(source)
                self.table.setItem(row, 0, url_item)

                for col, (key, value) in enumerate(result_data.items(), start=1):
                    item = QTableWidgetItem(str(value) if value else "")
                    self.table.setItem(row, col, item)

                self._results.append(result)

            self._update_stats()

            if results:
                print(f"Loaded {len(results)} previous results")
        except Exception as e:
            print(f"Failed to load results: {e}")

    def _refresh_table(self):
        """Rebuild table from _results data."""
        self.table.setRowCount(0)

        for result in self._results:
            row = self.table.rowCount()
            self.table.insertRow(row)

            source = result.get("source", "")
            data = result.get("data", {})
            status = result.get("status")

            url_item = QTableWidgetItem(source)
            self.table.setItem(row, 0, url_item)

            for col, (key, value) in enumerate(data.items(), start=1):
                item = QTableWidgetItem(str(value) if value else "")
                self.table.setItem(row, col, item)

            # Apply diff highlighting
            if status:
                color = {
                    "new": "#2d4a2d",
                    "changed": "#4a4a2d",
                    "removed": "#4a2d2d"
                }.get(status)

                if color:
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            item.setData(Qt.ItemDataRole.BackgroundRole, color)

        self._update_stats()

    def _confirm_clear(self):
        """Confirm before clearing all results."""
        if not self._results:
            QMessageBox.information(self, "No Results", "No results to clear.")
            return

        reply = QMessageBox.question(
            self,
            "Clear All Results",
            f"Are you sure you want to delete all {len(self._results)} results?\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.clear()
            self._save_results()  # Save empty state
