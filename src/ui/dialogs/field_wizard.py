"""Smart field naming wizard dialog for Parsonic."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QDialogButtonBox, QFrame
)
from PyQt6.QtCore import Qt


class FieldWizardDialog(QDialog):
    """Smart field naming dialog with intelligent suggestions."""

    def __init__(
        self,
        selector: str,
        element_info: dict,
        suggestions: list,
        parent=None
    ):
        super().__init__(parent)
        self.selector = selector
        self.element_info = element_info
        self.suggestions = suggestions

        self.selected_name = ""
        self.selected_attribute = None

        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Add Field")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Preview of selected element
        preview_group = QGroupBox("Selected Element")
        preview_layout = QFormLayout(preview_group)
        preview_layout.setSpacing(8)

        # Show selector (truncated if too long)
        selector_display = self.selector
        if len(selector_display) > 60:
            selector_display = selector_display[:57] + "..."
        selector_label = QLabel(selector_display)
        selector_label.setStyleSheet("color: #4ec9b0; font-family: monospace;")
        selector_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        preview_layout.addRow("Selector:", selector_label)

        # Show content preview
        text_preview = self.element_info.get("text", "")[:80]
        if text_preview:
            content_label = QLabel(f'"{text_preview}"')
            content_label.setStyleSheet("color: #969696; font-style: italic;")
            content_label.setWordWrap(True)
            preview_layout.addRow("Content:", content_label)

        # Show href if present
        href = self.element_info.get("href", "")
        if href:
            href_display = href if len(href) < 50 else href[:47] + "..."
            href_label = QLabel(href_display)
            href_label.setStyleSheet("color: #6a9955;")
            preview_layout.addRow("Link:", href_label)

        layout.addWidget(preview_group)

        # Suggestions section
        suggest_group = QGroupBox("What should we call this field?")
        suggest_layout = QVBoxLayout(suggest_group)
        suggest_layout.setSpacing(8)

        self.suggestion_group = QButtonGroup(self)

        # Add suggestions as radio buttons
        for i, suggestion in enumerate(self.suggestions[:4]):
            name = suggestion["name"]
            reason = suggestion.get("reason", "")
            confidence = suggestion.get("confidence", 0)

            # Create radio button with styled text
            radio = QRadioButton()
            radio.setProperty("suggestion", suggestion)

            # Create a widget for the radio content
            radio_layout = QHBoxLayout()
            radio_layout.setContentsMargins(0, 0, 0, 0)

            name_label = QLabel(f"<b>{name}</b>")
            radio_layout.addWidget(radio)
            radio_layout.addWidget(name_label)

            if reason:
                reason_label = QLabel(f"<span style='color: #969696;'>({reason})</span>")
                radio_layout.addWidget(reason_label)

            # Confidence indicator
            if confidence >= 0.9:
                conf_label = QLabel("✓")
                conf_label.setStyleSheet("color: #4ec9b0;")
                radio_layout.addWidget(conf_label)

            radio_layout.addStretch()

            container = QFrame()
            container.setLayout(radio_layout)
            suggest_layout.addWidget(container)

            self.suggestion_group.addButton(radio, i)

            if i == 0:
                radio.setChecked(True)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3c3c3c;")
        suggest_layout.addWidget(separator)

        # Custom name option
        custom_layout = QHBoxLayout()
        self.custom_radio = QRadioButton("Custom:")
        self.suggestion_group.addButton(self.custom_radio, -1)
        custom_layout.addWidget(self.custom_radio)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("Enter custom field name...")
        self.custom_input.textChanged.connect(self._on_custom_text_changed)
        custom_layout.addWidget(self.custom_input)

        suggest_layout.addLayout(custom_layout)

        layout.addWidget(suggest_group)

        # Attribute selection (for links, images)
        href = self.element_info.get("href", "")
        src = self.element_info.get("src", "")

        if href or src:
            attr_group = QGroupBox("What to extract?")
            attr_layout = QVBoxLayout(attr_group)

            self.attr_group = QButtonGroup(self)

            self.text_radio = QRadioButton("Text content (what you see on the page)")
            self.attr_group.addButton(self.text_radio, 0)
            attr_layout.addWidget(self.text_radio)

            if href:
                self.href_radio = QRadioButton(f"Link URL (href): {href[:50]}...")
                self.attr_group.addButton(self.href_radio, 1)
                attr_layout.addWidget(self.href_radio)
            else:
                self.href_radio = None

            if src:
                self.src_radio = QRadioButton(f"Image URL (src): {src[:50]}...")
                self.attr_group.addButton(self.src_radio, 2)
                attr_layout.addWidget(self.src_radio)
            else:
                self.src_radio = None

            # Pre-select based on top suggestion
            if self.suggestions and self.suggestions[0].get("attribute") == "href" and self.href_radio:
                self.href_radio.setChecked(True)
            elif self.suggestions and self.suggestions[0].get("attribute") == "src" and self.src_radio:
                self.src_radio.setChecked(True)
            else:
                self.text_radio.setChecked(True)

            layout.addWidget(attr_group)
        else:
            self.attr_group = None
            self.text_radio = None
            self.href_radio = None
            self.src_radio = None

        # Buttons
        button_layout = QHBoxLayout()

        # Add to Crawler button (for link elements)
        if self.element_info.get("href"):
            self.crawl_btn = QPushButton("Add to Crawler")
            self.crawl_btn.setToolTip("Use this selector as the crawl link selector")
            self.crawl_btn.clicked.connect(self._add_to_crawler)
            button_layout.addWidget(self.crawl_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Add Field")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._save_and_accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        # Track if we're adding to crawler
        self.add_to_crawler = False

    def _add_to_crawler(self):
        """Set this selector as the crawl link selector."""
        self.add_to_crawler = True
        self.accept()

    def _on_custom_text_changed(self, text):
        """Select custom radio when user types."""
        if text:
            self.custom_radio.setChecked(True)

    def _save_and_accept(self):
        """Save selections and accept dialog."""
        # Get selected name
        selected_id = self.suggestion_group.checkedId()

        if selected_id == -1 or selected_id >= len(self.suggestions):  # Custom or invalid
            self.selected_name = self.custom_input.text().strip()
            if not self.selected_name:
                self.selected_name = "field"
        else:
            suggestion = self.suggestions[selected_id]
            self.selected_name = suggestion["name"]

        # Sanitize name (replace spaces/special chars with underscore)
        self.selected_name = "".join(
            c if c.isalnum() or c == "_" else "_"
            for c in self.selected_name.lower()
        )

        # Get selected attribute
        if self.attr_group:
            attr_id = self.attr_group.checkedId()
            if attr_id == 1 and self.href_radio:
                self.selected_attribute = "href"
            elif attr_id == 2 and self.src_radio:
                self.selected_attribute = "src"
            else:
                self.selected_attribute = None
        else:
            self.selected_attribute = None

        self.accept()

    def get_result(self) -> dict:
        """Get the dialog result."""
        return {
            "name": self.selected_name,
            "selector": self.selector,
            "attribute": self.selected_attribute,
            "add_to_crawler": self.add_to_crawler,
        }
