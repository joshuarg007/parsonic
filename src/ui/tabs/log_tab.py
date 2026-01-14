"""Log viewer tab for Parsonic."""

from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton,
    QComboBox, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCharFormat, QColor, QFont


class LogTab(QWidget):
    """Tab for viewing scraper logs in real-time."""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """Build the log viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Info", "Warning", "Error", "Debug"])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter_combo)

        toolbar.addStretch()

        self.auto_scroll_btn = QPushButton("Auto-scroll: ON")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.setProperty("secondary", True)
        self.auto_scroll_btn.clicked.connect(self._toggle_auto_scroll)
        toolbar.addWidget(self.auto_scroll_btn)

        self.clear_btn = QPushButton("Clear Logs")
        self.clear_btn.setProperty("secondary", True)
        self.clear_btn.clicked.connect(self.clear)
        toolbar.addWidget(self.clear_btn)

        self.export_btn = QPushButton("Export Logs")
        self.export_btn.setProperty("secondary", True)
        self.export_btn.clicked.connect(self._export_logs)
        toolbar.addWidget(self.export_btn)

        layout.addLayout(toolbar)

        # Log viewer
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setProperty("logPanel", True)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Set monospace font
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_view.setFont(font)

        layout.addWidget(self.log_view)

        # Stats bar
        stats = QHBoxLayout()

        self.stats_label = QLabel("0 entries")
        stats.addWidget(self.stats_label)

        stats.addStretch()

        self.errors_label = QLabel("0 errors")
        self.errors_label.setStyleSheet("color: #f14c4c;")
        stats.addWidget(self.errors_label)

        self.warnings_label = QLabel("0 warnings")
        self.warnings_label.setStyleSheet("color: #cca700;")
        stats.addWidget(self.warnings_label)

        layout.addLayout(stats)

        # Internal state
        self._entries = []
        self._auto_scroll = True
        self._info_count = 0
        self._warning_count = 0
        self._error_count = 0

    def _timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def log_info(self, message: str):
        """Log an info message."""
        self._add_entry("INFO", message, "#3794ff")
        self._info_count += 1

    def log_warning(self, message: str):
        """Log a warning message."""
        self._add_entry("WARN", message, "#cca700")
        self._warning_count += 1
        self.warnings_label.setText(f"{self._warning_count} warnings")

    def log_error(self, message: str):
        """Log an error message."""
        self._add_entry("ERROR", message, "#f14c4c")
        self._error_count += 1
        self.errors_label.setText(f"{self._error_count} errors")

    def log_debug(self, message: str):
        """Log a debug message."""
        self._add_entry("DEBUG", message, "#6a9955")

    def log_request(self, method: str, url: str, status: int = None, time_ms: float = None):
        """Log an HTTP request."""
        status_str = f" [{status}]" if status else ""
        time_str = f" ({time_ms:.0f}ms)" if time_ms else ""
        color = "#3794ff" if status and status < 400 else "#f14c4c" if status else "#d4d4d4"
        self._add_entry("HTTP", f"{method} {url}{status_str}{time_str}", color)

    def _add_entry(self, level: str, message: str, color: str):
        """Add a log entry."""
        timestamp = self._timestamp()
        entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "color": color
        }
        self._entries.append(entry)

        # Format and append to view
        formatted = f"[{timestamp}] [{level:5}] {message}"
        self.log_view.appendHtml(f'<span style="color: {color};">{formatted}</span>')

        self.stats_label.setText(f"{len(self._entries)} entries")

        # Auto-scroll
        if self._auto_scroll:
            self.log_view.verticalScrollBar().setValue(
                self.log_view.verticalScrollBar().maximum()
            )

    def _toggle_auto_scroll(self, checked: bool):
        """Toggle auto-scroll behavior."""
        self._auto_scroll = checked
        self.auto_scroll_btn.setText(f"Auto-scroll: {'ON' if checked else 'OFF'}")

    def _apply_filter(self, index: int):
        """Apply log level filter."""
        filter_text = self.filter_combo.currentText().upper()

        self.log_view.clear()
        for entry in self._entries:
            if filter_text == "ALL" or entry["level"] == filter_text[:5]:
                formatted = f"[{entry['timestamp']}] [{entry['level']:5}] {entry['message']}"
                self.log_view.appendHtml(f'<span style="color: {entry["color"]};">{formatted}</span>')

    def _export_logs(self):
        """Export logs to file."""
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Logs",
            f"parsonic_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if path:
            try:
                with open(path, 'w') as f:
                    for entry in self._entries:
                        f.write(f"[{entry['timestamp']}] [{entry['level']:5}] {entry['message']}\n")
            except Exception as e:
                self.log_error(f"Failed to export logs: {e}")

    def clear(self):
        """Clear all log entries."""
        self._entries.clear()
        self.log_view.clear()
        self._info_count = 0
        self._warning_count = 0
        self._error_count = 0
        self.stats_label.setText("0 entries")
        self.errors_label.setText("0 errors")
        self.warnings_label.setText("0 warnings")
