"""Dialog for showing auto-detected fields."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QDialogButtonBox, QWidget
)
from PyQt6.QtCore import Qt


class DetectedFieldsDialog(QDialog):
    """Dialog showing auto-detected fields for user selection."""

    def __init__(self, detected_fields: list, parent=None):
        super().__init__(parent)
        self.detected_fields = detected_fields
        self.selected_fields = []
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Auto-Detected Fields")
        self.setMinimumSize(600, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Header
        header = QLabel(
            f"Found {len(self.detected_fields)} potential fields on this page.\n"
            "Select which ones to add:"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Table of detected fields
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Add", "Field Name", "Selector", "Found", "Sample"
        ])

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 60)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # Populate table
        self.checkboxes = []
        for field in self.detected_fields:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(True)  # Default to selected
            self.checkboxes.append(checkbox)

            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.addWidget(checkbox)
            self.table.setCellWidget(row, 0, checkbox_widget)

            # Field name
            name_item = QTableWidgetItem(field.get("name", ""))
            name_item.setForeground(Qt.GlobalColor.cyan)
            self.table.setItem(row, 1, name_item)

            # Selector
            selector = field.get("selector", "")
            selector_item = QTableWidgetItem(selector)
            selector_item.setForeground(Qt.GlobalColor.green)
            selector_item.setToolTip(selector)
            self.table.setItem(row, 2, selector_item)

            # Count
            count_item = QTableWidgetItem(str(field.get("count", 0)))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, count_item)

            # Sample
            sample = field.get("sample", "")
            if len(sample) > 50:
                sample = sample[:47] + "..."
            sample_item = QTableWidgetItem(sample)
            sample_item.setForeground(Qt.GlobalColor.gray)
            sample_item.setToolTip(field.get("sample", ""))
            self.table.setItem(row, 4, sample_item)

        layout.addWidget(self.table)

        # Select all / none buttons
        select_buttons = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.setProperty("secondary", True)
        select_all_btn.clicked.connect(self._select_all)
        select_buttons.addWidget(select_all_btn)

        select_none_btn = QPushButton("Select None")
        select_none_btn.setProperty("secondary", True)
        select_none_btn.clicked.connect(self._select_none)
        select_buttons.addWidget(select_none_btn)

        select_buttons.addStretch()

        layout.addLayout(select_buttons)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_all(self):
        """Select all checkboxes."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(True)

    def _select_none(self):
        """Deselect all checkboxes."""
        for checkbox in self.checkboxes:
            checkbox.setChecked(False)

    def _save_and_accept(self):
        """Save selected fields and accept dialog."""
        self.selected_fields = []
        for i, checkbox in enumerate(self.checkboxes):
            if checkbox.isChecked():
                self.selected_fields.append(self.detected_fields[i])
        self.accept()

    def get_selected_fields(self) -> list:
        """Get the list of selected fields."""
        return self.selected_fields
