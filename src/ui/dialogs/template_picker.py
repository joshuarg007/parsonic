"""Template picker dialog for Parsonic."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QDialogButtonBox,
    QComboBox, QFrame
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from src.core.templates import TEMPLATES, get_template


class TemplatePickerDialog(QDialog):
    """Dialog for selecting a scraper template."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_template_id = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("New from Template")
        self.setMinimumSize(650, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Header
        header = QLabel("Choose a template to get started quickly:")
        header.setProperty("heading", True)
        layout.addWidget(header)

        # Category filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Category:"))

        self.category_combo = QComboBox()
        self.category_combo.addItems(["All Templates", "Business", "E-commerce", "Content"])
        self.category_combo.currentTextChanged.connect(self._filter_templates)
        filter_layout.addWidget(self.category_combo)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Main content - split view
        content_layout = QHBoxLayout()

        # Template list
        self.template_list = QListWidget()
        self.template_list.setMinimumWidth(250)
        self.template_list.setSpacing(4)
        self.template_list.itemClicked.connect(self._on_template_selected)
        self.template_list.itemDoubleClicked.connect(self._on_template_double_clicked)
        content_layout.addWidget(self.template_list)

        # Details panel
        details_panel = QFrame()
        details_panel.setFrameShape(QFrame.Shape.StyledPanel)
        details_layout = QVBoxLayout(details_panel)
        details_layout.setSpacing(12)

        self.template_name_label = QLabel("Select a template")
        self.template_name_label.setProperty("heading", True)
        self.template_name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        details_layout.addWidget(self.template_name_label)

        self.template_desc_label = QLabel("")
        self.template_desc_label.setWordWrap(True)
        self.template_desc_label.setStyleSheet("color: #969696;")
        details_layout.addWidget(self.template_desc_label)

        # Fields preview
        fields_group = QGroupBox("Included Fields")
        fields_layout = QVBoxLayout(fields_group)

        self.fields_label = QLabel("")
        self.fields_label.setWordWrap(True)
        self.fields_label.setStyleSheet("color: #4ec9b0; font-family: monospace;")
        fields_layout.addWidget(self.fields_label)

        details_layout.addWidget(fields_group)

        # Rate limit info
        self.rate_label = QLabel("")
        self.rate_label.setStyleSheet("color: #6a9955; font-size: 11px;")
        details_layout.addWidget(self.rate_label)

        details_layout.addStretch()

        content_layout.addWidget(details_panel, stretch=1)
        layout.addLayout(content_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)

        # Disable OK until a template is selected
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)

        layout.addWidget(buttons)

        # Populate templates
        self._populate_templates()

    def _populate_templates(self):
        """Populate the template list."""
        self.template_list.clear()

        # Define categories for templates
        categories = {
            "ecommerce": "E-commerce",
            "news": "Content",
            "jobs": "Content",
            "realestate": "E-commerce",
            "social": "Content",
            "business_directory": "Business",
            "company_profile": "Business",
            "contact_person": "Business",
        }

        # Icons for different template types
        icons = {
            "business": "🏢",
            "ecommerce": "🛒",
            "news": "📰",
            "jobs": "💼",
            "realestate": "🏠",
            "social": "👤",
            "business_directory": "📒",
            "company_profile": "🏛️",
            "contact_person": "👤",
        }

        current_filter = self.category_combo.currentText()

        for template_id, template_info in TEMPLATES.items():
            category = categories.get(template_id, "Other")

            # Apply category filter
            if current_filter != "All Templates":
                if category != current_filter:
                    continue

            icon = icons.get(template_id, "📄")
            name = template_info.get("name", template_id)

            item = QListWidgetItem(f"{icon}  {name}")
            item.setData(Qt.ItemDataRole.UserRole, template_id)
            item.setSizeHint(QSize(200, 36))

            self.template_list.addItem(item)

    def _filter_templates(self, category: str):
        """Filter templates by category."""
        self._populate_templates()

    def _on_template_selected(self, item: QListWidgetItem):
        """Handle template selection."""
        template_id = item.data(Qt.ItemDataRole.UserRole)
        self.selected_template_id = template_id

        template_info = TEMPLATES.get(template_id, {})

        # Update name
        self.template_name_label.setText(template_info.get("name", template_id))

        # Update description
        self.template_desc_label.setText(template_info.get("description", ""))

        # Get template instance to show fields
        try:
            template = get_template(template_id)

            # Show fields
            field_names = [f.name for f in template.fields]
            self.fields_label.setText(" • ".join(field_names))

            # Show rate limit info
            rate = template.rate_limit
            self.rate_label.setText(
                f"Rate limit: {rate.min_delay}-{rate.max_delay}s delay, "
                f"{rate.max_concurrent} concurrent"
            )
        except Exception:
            self.fields_label.setText("Error loading template")
            self.rate_label.setText("")

        # Enable OK button
        self.ok_button.setEnabled(True)

    def _on_template_double_clicked(self, item: QListWidgetItem):
        """Handle double-click to select and confirm."""
        self._on_template_selected(item)
        self._save_and_accept()

    def _save_and_accept(self):
        """Save selection and accept dialog."""
        if self.selected_template_id:
            self.accept()

    def get_selected_template_id(self) -> str:
        """Get the selected template ID."""
        return self.selected_template_id
