"""Combined scrape tab with URL management, browser preview, and field selection."""

import asyncio
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QTextEdit, QPlainTextEdit, QFrame, QMessageBox, QDialog,
    QDialogButtonBox, QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFileDialog, QScrollArea
)
from PyQt6.QtCore import pyqtSignal, Qt, QUrl, QThread, QObject, pyqtSlot
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

from src.models.project import ScraperProject, SelectorField, SiteType
from src.core.scraper import ScraperOrchestrator
from src.core.field_detection import suggest_field_name
from src.ui.dialogs.field_wizard import FieldWizardDialog


class SelectorBridge(QObject):
    """Bridge between JavaScript and Python for element selection."""

    element_selected = pyqtSignal(str, str, str)  # selector, xpath, text_preview

    def __init__(self):
        super().__init__()

    @pyqtSlot(str, str, str)
    def onElementSelected(self, css_selector: str, xpath: str, preview: str):
        """Called from JavaScript when user clicks an element."""
        self.element_selected.emit(css_selector, xpath, preview)


class AIAnalyzeWorker(QThread):
    """Background worker for AI page analysis with optional deep link following."""

    finished = pyqtSignal(list)  # List[DetectedField]
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, elements: list, url: str, deep_links: list = None, depth: int = 1):
        super().__init__()
        self.elements = elements  # List of {selector, text, tag, classes}
        self.url = url
        self.deep_links = deep_links or []
        self.depth = depth  # 1=page only, 2+=follow links

    def run(self):
        try:
            from src.core.llm_enrichment import get_enricher
            import requests
            from bs4 import BeautifulSoup

            enricher = get_enricher()

            # Check if Ollama is available
            available, message = enricher.check_ollama_available()
            if not available:
                self.error.emit(f"Ollama not available: {message}")
                return

            all_elements = list(self.elements)  # Start with main page elements

            # Deep mode: fetch linked pages and extract elements
            # Number of links scales with depth: depth 2=5, depth 3=10, depth 4=15, depth 5=20
            if self.deep_links and self.depth > 1:
                max_links = self.depth * 5 - 5  # depth 2=5, 3=10, 4=15, 5=20
                links_to_fetch = self.deep_links[:max_links]
                total = len(links_to_fetch)
                for i, link_url in enumerate(links_to_fetch):
                    self.progress.emit(f"Page {i+1}/{total}...")
                    try:
                        resp = requests.get(link_url, timeout=10, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        })
                        if resp.status_code == 200:
                            link_elements = self._extract_elements_from_html(resp.text)
                            all_elements.extend(link_elements)
                    except Exception:
                        continue

            self.progress.emit("Classifying elements...")

            # Classify all collected elements
            fields = self._classify_elements(enricher, all_elements, self.url)

            if not fields:
                self.error.emit("No fields detected. Try a different page or use manual selection.")
                return

            self.finished.emit(fields)

        except Exception as e:
            self.error.emit(f"AI analysis failed: {str(e)}")

    def _extract_elements_from_html(self, html: str) -> list:
        """Extract elements from HTML using BeautifulSoup (for deep mode)."""
        try:
            from bs4 import BeautifulSoup
            import re

            soup = BeautifulSoup(html, 'html.parser')
            elements = []
            seen = set()

            # Remove nav/header/footer
            for tag in soup.find_all(['nav', 'header', 'footer']):
                tag.decompose()

            # Extract headings
            for el in soup.find_all(['h1', 'h2']):
                text = el.get_text(strip=True)
                if text and len(text) > 2 and text not in seen:
                    seen.add(text)
                    selector = el.name
                    if el.get('class'):
                        selector += '.' + '.'.join(el.get('class')[:2])
                    elements.append({
                        'selector': selector,
                        'text': text[:150],
                        'tag': el.name,
                        'priority': 'heading'
                    })

            # Extract tel/mailto links
            for el in soup.find_all('a', href=True):
                href = el.get('href', '')
                if 'tel:' in href or 'mailto:' in href:
                    text = el.get_text(strip=True) or href
                    if text not in seen:
                        seen.add(text)
                        selector = 'a'
                        if el.get('class'):
                            selector += '.' + '.'.join(el.get('class')[:2])
                        elements.append({
                            'selector': selector,
                            'text': text[:100],
                            'tag': 'a',
                            'priority': 'phone' if 'tel:' in href else 'email',
                            'href': href
                        })

            return elements
        except Exception:
            return []

    def _classify_elements(self, enricher, elements: list, url: str) -> list:
        """Classify elements - auto-detect obvious fields, use AI for the rest."""
        from src.core.llm_enrichment import DetectedField
        import re

        fields = []
        seen_names = set()
        used_indices = set()

        # PHASE 1: Auto-detect obvious fields (no AI needed)
        for i, el in enumerate(elements):
            text = el.get('text', '').strip()
            priority = el.get('priority', '')
            href = el.get('href', '')

            if not text:
                continue

            # Phone from tel: links
            if priority == 'phone' or 'tel:' in href:
                if 'phone' not in seen_names:
                    phone_text = href.replace('tel:', '').split('?')[0] if 'tel:' in href else text
                    seen_names.add('phone')
                    used_indices.add(i)
                    fields.append(DetectedField(
                        name='phone',
                        selector=el.get('selector', ''),
                        sample_value=phone_text[:50],
                        confidence=0.95,
                        field_type='link' if href else 'text',
                        attribute='href' if 'tel:' in href else None
                    ))

            # Email from mailto: links
            elif priority == 'email' or 'mailto:' in href:
                if 'email' not in seen_names:
                    email_text = href.replace('mailto:', '').split('?')[0] if 'mailto:' in href else text
                    if '@' in email_text:
                        seen_names.add('email')
                        used_indices.add(i)
                        fields.append(DetectedField(
                            name='email',
                            selector=el.get('selector', ''),
                            sample_value=email_text[:50],
                            confidence=0.95,
                            field_type='link',
                            attribute='href'
                        ))

            # Company name from headings (h1, h2)
            elif priority == 'heading':
                if 'company_name' not in seen_names:
                    # Basic validation - not too short, not a UI/nav word
                    forbidden = r'^(home|about|contact|results|search|menu|follow\s*us|connect|share|social|subscribe|newsletter|sign\s*up|log\s*in|register|cart|checkout|shop|blog|news|faq|help|support|privacy|terms|copyright|all\s*rights)$'
                    if len(text) >= 3 and not re.match(forbidden, text, re.I):
                        seen_names.add('company_name')
                        used_indices.add(i)
                        fields.append(DetectedField(
                            name='company_name',
                            selector=el.get('selector', ''),
                            sample_value=text[:100],
                            confidence=0.9,
                            field_type='text',
                            attribute=None
                        ))

        # Second pass: Look for address in ALL elements (not just unmatched)
        # Address is often unlabeled but near phone/email
        if 'address' not in seen_names:
            for i, el in enumerate(elements):
                if i in used_indices:
                    continue
                text = el.get('text', '').strip()
                if not text or len(text) < 10 or len(text) > 200:
                    continue

                # Check for address patterns
                has_street = re.search(r'\b(ST|AVE|BLVD|RD|DR|LN|CT|WAY|PL|STREET|AVENUE|ROAD|DRIVE|LANE|COURT|CIRCLE|CIR)\b', text, re.I)
                has_zip = re.search(r'\b\d{5}(-\d{4})?\b', text)
                has_city_state = re.search(r',\s*[A-Z]{2}\s*\d{5}', text)  # ", CO 80122"
                has_number_start = re.search(r'^\d+\s+[A-Za-z]', text)  # Starts with street number
                has_city_comma = re.search(r',\s*[A-Z][a-z]+', text)  # ", Denver" or ", Miami"

                # Count indicators
                indicators = sum([bool(has_street), bool(has_zip), bool(has_city_state), bool(has_number_start), bool(has_city_comma)])

                # Accept if: starts with number + has street word, OR has zip + city/state, OR 2+ indicators
                is_address = False
                if has_number_start and has_street:
                    is_address = True
                elif has_zip and (has_city_state or has_city_comma):
                    is_address = True
                elif indicators >= 2:
                    is_address = True

                if is_address:
                    seen_names.add('address')
                    used_indices.add(i)
                    fields.append(DetectedField(
                        name='address',
                        selector=el.get('selector', ''),
                        sample_value=text[:150],
                        confidence=0.85,
                        field_type='text',
                        attribute=None
                    ))
                    break  # Only need one address

        # If we found the priority fields, return without AI
        if 'company_name' in seen_names and 'phone' in seen_names:
            return fields

        # PHASE 2: Use AI for remaining/ambiguous elements (only if needed)
        remaining_elements = [(i, el) for i, el in enumerate(elements) if i not in used_indices]
        if not remaining_elements or len(remaining_elements) > 50:
            return fields  # Skip AI if nothing left or too many

        def validate_field(name: str, text: str) -> bool:
            """Check if text is valid for the field type."""
            text = text.strip()
            if not text:
                return False

            if name == 'phone':
                # Must look like a phone number, not an address
                # Reject if contains street indicators
                if re.search(r'\b(ST|AVE|BLVD|RD|DR|LN|CT|WAY|PL|STREET|AVENUE|ROAD|DRIVE)\b', text, re.I):
                    return False
                # Reject if contains state abbreviations or zip-like patterns at end
                if re.search(r',\s*[A-Z]{2},?\s*\d{5}', text):
                    return False
                # Must have a contiguous group of 7+ digits (with allowed separators)
                # Phone pattern: optional +, then digits with -, (), spaces
                phone_pattern = r'^\+?[\d\s\-\(\)\.]{7,20}$'
                if re.match(phone_pattern, text):
                    digits = re.sub(r'\D', '', text)
                    return 7 <= len(digits) <= 15
                # Also accept patterns like (555) 123-4567 or 555-123-4567
                if re.search(r'\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}', text):
                    return True
                return False

            elif name == 'email':
                # Must contain @ and . with proper structure
                if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
                    return True
                return False

            elif name == 'company_name':
                # Must have letters, not just numbers/symbols, reasonable length
                has_letters = bool(re.search(r'[a-zA-Z]{2,}', text))
                not_just_numbers = not re.match(r'^[\d\s\-\.\,]+$', text)
                reasonable_length = 3 <= len(text) <= 150
                # Not common nav/UI words
                bad_words = r'^(home|about|contact|menu|login|sign|blog|news|faq|results|search|filter|sort|view|show|hide|more|less|back|next|prev|submit|cancel|close|open|click|here|loading|error|success|warning|info|details|description|overview|summary|field|value|name|title|header|footer|sidebar|content|main|page|site|web|follow\s*us|connect|share|social|subscribe|newsletter|register|cart|checkout|shop|help|support|privacy|terms|copyright|all\s*rights)$'
                not_nav = not re.match(bad_words, text, re.I)
                # Not an address
                not_address = not re.search(r'\b(ST|AVE|BLVD|RD|DR|LN|CT|STREET|AVENUE)\b', text, re.I)
                not_address = not_address and not re.search(r',\s*[A-Z]{2},?\s*\d{5}', text)
                return has_letters and not_just_numbers and reasonable_length and not_nav and not_address

            elif name == 'address':
                # Should have street indicators or city/state/zip pattern
                has_street = bool(re.search(r'\b(ST|AVE|BLVD|RD|DR|LN|CT|WAY|PL|STREET|AVENUE|ROAD|DRIVE)\b', text, re.I))
                has_zip = bool(re.search(r'\b\d{5}(-\d{4})?\b', text))
                has_city_state = bool(re.search(r',\s*[A-Z]{2}\b', text, re.I))
                return (has_street or has_zip or has_city_state) and len(text) >= 10

            elif name == 'website':
                # Should look like a URL or domain
                return bool(re.search(r'(https?://|www\.|\.com|\.org|\.net)', text, re.I))

            elif name in ('rating', 'reviews'):
                # Should have numbers or stars, be short
                return bool(re.search(r'[\d★☆⭐]', text)) and len(text) <= 50

            elif name == 'category':
                # Should be text, not numbers, not an address
                if re.search(r'\b(ST|AVE|BLVD|RD|STREET|AVENUE)\b', text, re.I):
                    return False
                if re.search(r',\s*[A-Z]{2},?\s*\d{5}', text):
                    return False
                return bool(re.search(r'[a-zA-Z]{3,}', text)) and len(text) <= 100

            elif name == 'description':
                # Should be longer text with multiple words (20+ words, not just characters)
                word_count = len(text.split())
                has_letters = bool(re.search(r'[a-zA-Z]{3,}', text))
                # Must be actual sentences, not just a name
                return word_count >= 10 and has_letters and len(text) >= 50

            # Default: accept if has some letters
            return bool(re.search(r'[a-zA-Z]', text))

        # Build list from remaining elements only
        element_list = []
        index_map = {}  # Map list index to original element index
        for list_idx, (orig_idx, el) in enumerate(remaining_elements[:50]):
            text = el.get('text', '').strip()[:100]
            if not text:
                continue
            tag = el.get('tag', 'div')
            element_list.append(f"{list_idx}. [{tag}] {text}")
            index_map[list_idx] = orig_idx

        if not element_list:
            return fields  # Return what we auto-detected

        elements_text = "\n".join(element_list)

        # Only ask AI for fields we haven't found yet
        missing = []
        if 'company_name' not in seen_names:
            missing.append('"company_name" = business name')
        if 'phone' not in seen_names:
            missing.append('"phone" = phone number')
        if 'email' not in seen_names:
            missing.append('"email" = email address')
        missing.extend(['"address" = street address', '"category" = business type'])

        prompt = f"""Find these fields in the elements:
{chr(10).join(missing)}

Elements:
{elements_text}

SKIP navigation links and UI labels.

Output: {{"fields": [{{"index": 0, "name": "company_name"}}]}}
"name" must be one of: company_name, phone, email, address, category
JSON only:"""

        response = enricher._call_ollama(
            enricher.config.classification_model,
            prompt,
            "Output JSON only. Field names: company_name, phone, email, address, category."
        )

        parsed = enricher._parse_json_response(response)

        # Only accept these valid field type names
        valid_field_types = {'company_name', 'phone', 'email', 'address', 'website', 'description', 'category'}

        if parsed and "fields" in parsed:
            for item in parsed["fields"]:
                try:
                    list_idx = int(item.get("index", -1))
                    orig_idx = index_map.get(list_idx, -1)
                    if orig_idx >= 0 and orig_idx < len(elements):
                        el = elements[orig_idx]
                        name = item.get("name", "")

                        # Skip if not a valid field type
                        if name not in valid_field_types:
                            continue

                        # Skip if already found
                        if name in seen_names:
                            continue

                        text = el.get("text", "")

                        # Validate the field matches its type
                        # For email, also check href
                        if name == 'email':
                            href = el.get('href', '')
                            if 'mailto:' in href:
                                # Extract actual email from href
                                text = href.replace('mailto:', '').split('?')[0]
                            elif not ('@' in text and '.' in text):
                                continue
                        elif not validate_field(name, text):
                            continue

                        seen_names.add(name)

                        # Determine attribute for links
                        attr = None
                        href = el.get('href', '')
                        if href:
                            # For mailto/tel links, we want the href content
                            if 'mailto:' in href or 'tel:' in href:
                                attr = "href"

                        fields.append(DetectedField(
                            name=name,
                            selector=el.get("selector", ""),
                            sample_value=text[:100],
                            confidence=0.9 if el.get('priority') in ('heading', 'phone', 'email') else 0.7,
                            field_type="link" if href else "text",
                            attribute=attr
                        ))
                except (ValueError, TypeError, IndexError):
                    continue

        return fields


class ScrapeTab(QWidget):
    """Combined tab for URL management, browser preview, and field selection."""

    project_changed = pyqtSignal()
    run_scrape_requested = pyqtSignal()  # Signal to trigger scrape in main window

    # JavaScript for element selection overlay
    SELECTOR_JS = """
    (function() {
        if (window.parsonicInjected) return;
        window.parsonicInjected = true;
        window.parsonicSelectMode = true;

        let overlay = document.createElement('div');
        overlay.id = 'parsonic-overlay';
        overlay.style.cssText = 'position:fixed;pointer-events:none;border:2px solid #007acc;background:rgba(0,122,204,0.1);z-index:999999;display:none;transition:all 0.1s;';
        document.body.appendChild(overlay);

        let lastElement = null;

        function getSelector(el) {
            if (el.id) return '#' + el.id;

            let path = [];
            while (el && el.nodeType === Node.ELEMENT_NODE) {
                let selector = el.tagName.toLowerCase();
                if (el.className && typeof el.className === 'string') {
                    let classes = el.className.trim().split(/\\s+/).filter(c => c && !c.startsWith('parsonic') && !c.match(/^(active|open|hover|selected|focus)/));
                    if (classes.length) selector += '.' + classes.slice(0, 2).join('.');
                }
                // Don't add :nth-of-type - keep selectors generic for reuse across pages
                path.unshift(selector);
                el = el.parentNode;
                if (path.length > 4) break;
            }
            return path.join(' > ');
        }

        function getXPath(el) {
            if (el.id) return '//*[@id="' + el.id + '"]';

            let path = [];
            while (el && el.nodeType === Node.ELEMENT_NODE) {
                let index = 1;
                let sibling = el.previousSibling;
                while (sibling) {
                    if (sibling.nodeType === Node.ELEMENT_NODE && sibling.tagName === el.tagName) index++;
                    sibling = sibling.previousSibling;
                }
                path.unshift(el.tagName.toLowerCase() + '[' + index + ']');
                el = el.parentNode;
                if (path.length > 6) break;
            }
            return '//' + path.join('/');
        }

        document.addEventListener('mouseover', function(e) {
            if (!window.parsonicSelectMode) return;
            if (e.target === overlay) return;
            lastElement = e.target;
            let rect = e.target.getBoundingClientRect();
            overlay.style.display = 'block';
            overlay.style.left = rect.left + 'px';
            overlay.style.top = rect.top + 'px';
            overlay.style.width = rect.width + 'px';
            overlay.style.height = rect.height + 'px';
        });

        document.addEventListener('mouseout', function(e) {
            if (!e.relatedTarget || e.relatedTarget === document.documentElement) {
                overlay.style.display = 'none';
            }
        });

        document.addEventListener('click', function(e) {
            if (!window.parsonicSelectMode) return;

            e.preventDefault();
            e.stopPropagation();

            if (lastElement && window.bridge) {
                let css = getSelector(lastElement);
                let xpath = getXPath(lastElement);
                let preview = lastElement.textContent.trim().substring(0, 100);
                window.bridge.onElementSelected(css, xpath, preview);
            }
        }, true);
    })();
    """

    def __init__(self, project: ScraperProject):
        super().__init__()
        self.project = project
        self._setup_ui()

    def _setup_ui(self):
        """Build the combined scrape UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top bar - URL input with actions
        url_bar = QHBoxLayout()
        url_bar.setSpacing(4)

        # Back/Forward buttons
        self.back_btn = QPushButton("<")
        self.back_btn.setFixedWidth(30)
        self.back_btn.setToolTip("Go back")
        self.back_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.back_btn.clicked.connect(lambda: self.web_view.back())
        url_bar.addWidget(self.back_btn)

        self.forward_btn = QPushButton(">")
        self.forward_btn.setFixedWidth(30)
        self.forward_btn.setToolTip("Go forward")
        self.forward_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.forward_btn.clicked.connect(lambda: self.web_view.forward())
        url_bar.addWidget(self.forward_btn)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter URL to scrape (e.g., https://example.com/page/{1-10})")
        self.url_input.returnPressed.connect(self._load_url)
        url_bar.addWidget(self.url_input, 1)

        self.add_url_btn = QPushButton("Add")
        self.add_url_btn.setToolTip("Add URL to scrape queue")
        self.add_url_btn.clicked.connect(self._add_url_to_queue)
        url_bar.addWidget(self.add_url_btn)

        self.load_btn = QPushButton("Load")
        self.load_btn.setToolTip("Load URL in browser preview")
        self.load_btn.clicked.connect(self._load_url)
        url_bar.addWidget(self.load_btn)

        self.select_mode_btn = QPushButton("Select Mode: OFF")
        self.select_mode_btn.setCheckable(True)
        self.select_mode_btn.setProperty("secondary", True)
        self.select_mode_btn.clicked.connect(self._toggle_select_mode)
        url_bar.addWidget(self.select_mode_btn)

        # URL count badge
        self.url_count_label = QLabel("URLs: 0")
        self.url_count_label.setStyleSheet("color: #888; font-size: 11px;")
        url_bar.addWidget(self.url_count_label)

        layout.addLayout(url_bar)

        # Main splitter - horizontal
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter, 1)

        # Left panel - Browser
        browser_panel = QWidget()
        browser_layout = QVBoxLayout(browser_panel)
        browser_layout.setContentsMargins(0, 0, 4, 0)
        browser_layout.setSpacing(4)

        # Web view
        self.web_view = QWebEngineView()
        self.web_view.urlChanged.connect(self._on_url_changed)
        self._load_welcome_page()
        browser_layout.addWidget(self.web_view)

        # Setup web channel for JS-Python communication
        self.channel = QWebChannel()
        self.bridge = SelectorBridge()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.bridge.element_selected.connect(self._on_element_selected)

        main_splitter.addWidget(browser_panel)

        # Right panel - Scrollable with collapsible sections
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(8)

        # === Fields Section (collapsible) ===
        self.fields_group = QGroupBox("Extraction Fields")
        self.fields_group.setCheckable(True)
        self.fields_group.setChecked(True)  # Expanded by default
        fields_layout = QVBoxLayout(self.fields_group)

        fields_buttons = QHBoxLayout()
        self.ai_analyze_btn = QPushButton("AI Analyze")
        self.ai_analyze_btn.setToolTip("Detect business fields on current page (company name, phone, email, address)")
        self.ai_analyze_btn.clicked.connect(self._ai_analyze_fields)
        fields_buttons.addWidget(self.ai_analyze_btn)

        self.add_field_btn = QPushButton("+ Add Field")
        self.add_field_btn.clicked.connect(self._add_field)
        fields_buttons.addWidget(self.add_field_btn)
        fields_buttons.addStretch()
        fields_layout.addLayout(fields_buttons)

        self.fields_table = QTableWidget()
        self.fields_table.setColumnCount(5)
        self.fields_table.setHorizontalHeaderLabels(["Field Name", "Selector", "Type", "Attr", ""])
        self.fields_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.fields_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.fields_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.fields_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.fields_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.fields_table.setColumnWidth(0, 100)
        self.fields_table.setColumnWidth(2, 55)
        self.fields_table.setColumnWidth(3, 50)
        self.fields_table.setColumnWidth(4, 70)
        self.fields_table.setAlternatingRowColors(True)
        self.fields_table.cellChanged.connect(self._on_field_changed)
        self.fields_table.setMinimumHeight(150)
        fields_layout.addWidget(self.fields_table)

        right_layout.addWidget(self.fields_group)

        # === Preview / Run (collapsible) ===
        self.preview_group = QGroupBox("Preview & Run")
        self.preview_group.setCheckable(True)
        self.preview_group.setChecked(True)  # Expanded by default
        preview_layout = QVBoxLayout(self.preview_group)

        preview_buttons = QHBoxLayout()
        self.test_btn = QPushButton("Test")
        self.test_btn.setToolTip("Test selectors on current page (F5)")
        self.test_btn.clicked.connect(self._test_selectors)
        preview_buttons.addWidget(self.test_btn)

        self.run_btn = QPushButton("Run Scrape")
        self.run_btn.setToolTip("Scrape all URLs in queue (F6)")
        self.run_btn.setStyleSheet("background-color: #2d8a4e; font-weight: bold;")
        self.run_btn.clicked.connect(self._run_scrape)
        preview_buttons.addWidget(self.run_btn)
        preview_buttons.addStretch()
        preview_layout.addLayout(preview_buttons)

        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(2)
        self.preview_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.preview_table.setColumnWidth(0, 100)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setMinimumHeight(100)
        preview_layout.addWidget(self.preview_table)

        right_layout.addWidget(self.preview_group)

        # === Auto-Crawl (collapsible, right after Preview) ===
        self.crawl_group = QGroupBox("Auto-Crawl")
        self.crawl_group.setCheckable(True)
        self.crawl_group.setChecked(False)
        crawl_layout = QFormLayout(self.crawl_group)
        crawl_layout.setSpacing(6)

        self.crawl_enabled = QCheckBox("Enable crawling")
        self.crawl_enabled.setToolTip("Follow links matching the selector to find more pages")
        self.crawl_enabled.stateChanged.connect(self._on_settings_changed)
        crawl_layout.addRow(self.crawl_enabled)

        self.link_selectors_edit = QPlainTextEdit()
        self.link_selectors_edit.setPlaceholderText("CSS selectors (one per line)\ne.g., a.listing-link\n.pagination a.next")
        self.link_selectors_edit.setToolTip("Enter one selector per line.\nUse for business links AND pagination (Next button)")
        self.link_selectors_edit.setMaximumHeight(60)
        self.link_selectors_edit.textChanged.connect(self._on_settings_changed)
        crawl_layout.addRow("Link selectors:", self.link_selectors_edit)

        self.max_pages_spin = QSpinBox()
        self.max_pages_spin.setRange(1, 10000)
        self.max_pages_spin.setValue(100)
        self.max_pages_spin.setToolTip("Maximum pages to crawl")
        self.max_pages_spin.valueChanged.connect(self._on_settings_changed)
        crawl_layout.addRow("Max pages:", self.max_pages_spin)

        self.same_domain = QCheckBox("Same domain only")
        self.same_domain.setChecked(True)
        self.same_domain.setToolTip("Only follow links on the same domain")
        self.same_domain.stateChanged.connect(self._on_settings_changed)
        crawl_layout.addRow(self.same_domain)

        right_layout.addWidget(self.crawl_group)

        # === Fallback Selectors (collapsible) ===
        self.fallback_group = QGroupBox("Fallback Selectors")
        self.fallback_group.setCheckable(True)
        self.fallback_group.setChecked(False)
        fallback_layout = QVBoxLayout(self.fallback_group)

        fallback_help = QLabel("Backup selectors if primary fails (one per line)")
        fallback_help.setStyleSheet("color: #888; font-size: 11px;")
        fallback_layout.addWidget(fallback_help)

        self.fallback_edit = QTextEdit()
        self.fallback_edit.setPlaceholderText("e.g., h1.title\n.company-name\n[itemprop='name']")
        self.fallback_edit.setMinimumHeight(60)
        self.fallback_edit.textChanged.connect(self._on_fallback_changed)
        fallback_layout.addWidget(self.fallback_edit)

        right_layout.addWidget(self.fallback_group)

        # === URL Queue (collapsible) ===
        self.urls_group = QGroupBox("URL Queue")
        self.urls_group.setCheckable(True)
        self.urls_group.setChecked(False)
        urls_layout = QVBoxLayout(self.urls_group)

        self.url_list = QTableWidget()
        self.url_list.setColumnCount(1)
        self.url_list.setHorizontalHeaderLabels(["URL"])
        self.url_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.url_list.setMinimumHeight(80)
        self.url_list.setAlternatingRowColors(True)
        urls_layout.addWidget(self.url_list)

        url_actions = QHBoxLayout()
        self.import_btn = QPushButton("Import")
        self.import_btn.setProperty("secondary", True)
        self.import_btn.clicked.connect(self._import_urls)
        url_actions.addWidget(self.import_btn)

        self.clear_urls_btn = QPushButton("Clear")
        self.clear_urls_btn.setProperty("secondary", True)
        self.clear_urls_btn.clicked.connect(self._clear_urls)
        url_actions.addWidget(self.clear_urls_btn)
        url_actions.addStretch()
        urls_layout.addLayout(url_actions)

        right_layout.addWidget(self.urls_group)

        # === Rate Limiting (collapsible) ===
        self.settings_group = QGroupBox("Rate Limiting")
        self.settings_group.setCheckable(True)
        self.settings_group.setChecked(False)
        settings_layout = QFormLayout(self.settings_group)
        settings_layout.setSpacing(6)

        delay_layout = QHBoxLayout()
        self.min_delay = QDoubleSpinBox()
        self.min_delay.setRange(0, 60)
        self.min_delay.setValue(1)
        self.min_delay.setSuffix("s")
        self.min_delay.setMaximumWidth(70)
        self.min_delay.valueChanged.connect(self._on_settings_changed)
        delay_layout.addWidget(self.min_delay)
        delay_layout.addWidget(QLabel("to"))
        self.max_delay = QDoubleSpinBox()
        self.max_delay.setRange(0, 60)
        self.max_delay.setValue(3)
        self.max_delay.setSuffix("s")
        self.max_delay.setMaximumWidth(70)
        self.max_delay.valueChanged.connect(self._on_settings_changed)
        delay_layout.addWidget(self.max_delay)
        delay_layout.addStretch()
        settings_layout.addRow("Delay:", delay_layout)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 20)
        self.concurrent_spin.setValue(3)
        self.concurrent_spin.setMaximumWidth(70)
        self.concurrent_spin.valueChanged.connect(self._on_settings_changed)
        settings_layout.addRow("Concurrent:", self.concurrent_spin)

        right_layout.addWidget(self.settings_group)

        right_layout.addStretch()

        scroll_area.setWidget(right_panel)
        main_splitter.addWidget(scroll_area)
        main_splitter.setSizes([550, 450])

        # State
        self._select_mode = False
        self._selected_field_row = -1
        self._field_fallbacks = {}
        self._url_queue = []

        # Connect table selection to load fallbacks
        self.fields_table.itemSelectionChanged.connect(self._on_field_selection_changed)

        # Make group boxes actually collapse when unchecked
        for group in [self.fields_group, self.fallback_group, self.urls_group,
                      self.crawl_group, self.settings_group, self.preview_group]:
            group.toggled.connect(lambda checked, g=group: self._toggle_group(g, checked))
            # Initialize collapsed state
            if not group.isChecked():
                self._toggle_group(group, False)

    def _toggle_group(self, group: QGroupBox, checked: bool):
        """Show/hide group box contents when toggled."""
        for child in group.findChildren(QWidget):
            if child.parent() == group:
                child.setVisible(checked)

    def _on_url_changed(self, url: QUrl):
        """Update URL bar when browser navigates."""
        url_str = url.toString()
        if url_str and not url_str.startswith(("about:", "data:")):
            self.url_input.setText(url_str)

        # Reset select mode state when navigating - page JS is cleared on navigation
        # so our injected script is gone. Reset UI to match.
        if self._select_mode:
            self._select_mode = False
            self.select_mode_btn.setChecked(False)
            self.select_mode_btn.setText("Select Mode: OFF")

    def _load_welcome_page(self):
        """Load a dark-themed welcome page."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    background: #1a1a2e;
                    color: #888;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    text-align: center;
                }
                h1 {
                    color: #4ec9b0;
                    font-size: 2.5em;
                    margin-bottom: 0.5em;
                    font-weight: 300;
                }
                p {
                    font-size: 1.1em;
                    line-height: 1.8;
                    max-width: 400px;
                }
                .step {
                    color: #6a9955;
                    font-family: monospace;
                }
                .key {
                    background: #2d2d4a;
                    padding: 2px 8px;
                    border-radius: 4px;
                    color: #ddd;
                    font-size: 0.9em;
                }
            </style>
        </head>
        <body>
            <h1>Parsonic</h1>
            <p>
                <span class="step">1.</span> Enter a URL above and click <span class="key">Load</span><br>
                <span class="step">2.</span> Click <span class="key">Select Mode: ON</span><br>
                <span class="step">3.</span> Click elements to extract<br>
                <span class="step">4.</span> Press <span class="key">F5</span> to test
            </p>
        </body>
        </html>
        """
        self.web_view.setHtml(html)

    def _load_url(self):
        """Load URL in the browser preview."""
        url = self.url_input.text().strip()
        if url:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            self.web_view.setUrl(QUrl(url))

    def _add_url_to_queue(self):
        """Add URL to the scrape queue."""
        url = self.url_input.text().strip()
        if not url:
            return

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Handle URL patterns like {1-10}
        if "{" in url and "-" in url:
            urls = self._expand_url_pattern(url)
        else:
            urls = [url]

        for u in urls:
            if u not in self._url_queue:
                self._url_queue.append(u)
                row = self.url_list.rowCount()
                self.url_list.insertRow(row)
                self.url_list.setItem(row, 0, QTableWidgetItem(u))

        self._update_url_count()
        self._sync_to_project()
        self.project_changed.emit()

        # Also load in browser if first URL
        if len(self._url_queue) == 1:
            self.web_view.setUrl(QUrl(urls[0]))

    def _expand_url_pattern(self, pattern: str) -> list[str]:
        """Expand URL pattern like https://example.com/page/{1-10}."""
        match = re.search(r'\{(\d+)-(\d+)\}', pattern)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            urls = []
            for i in range(start, end + 1):
                urls.append(re.sub(r'\{\d+-\d+\}', str(i), pattern))
            return urls
        return [pattern]

    def _import_urls(self):
        """Import URLs from a text file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import URLs", "",
            "Text Files (*.txt);;All Files (*)"
        )

        if path:
            try:
                with open(path, 'r') as f:
                    for line in f:
                        url = line.strip()
                        if url and not url.startswith('#'):
                            if url not in self._url_queue:
                                self._url_queue.append(url)
                                row = self.url_list.rowCount()
                                self.url_list.insertRow(row)
                                self.url_list.setItem(row, 0, QTableWidgetItem(url))

                self._update_url_count()
                self._sync_to_project()
                self.project_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Import Error", f"Failed to import URLs: {e}")

    def _clear_urls(self):
        """Clear all URLs from the queue."""
        self._url_queue = []
        self.url_list.setRowCount(0)
        self._update_url_count()
        self._sync_to_project()
        self.project_changed.emit()

    def _update_url_count(self):
        """Update the URL count label."""
        count = len(self._url_queue)
        self.url_count_label.setText(f"URLs: {count}")
        if count > 0:
            self.url_count_label.setStyleSheet("color: #4ec9b0; font-size: 11px; font-weight: bold;")
        else:
            self.url_count_label.setStyleSheet("color: #888; font-size: 11px;")

    def _use_selector_for_crawl(self):
        """Use the selected field's selector as the crawl link selector."""
        selected = self.fields_table.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "No Selection",
                "Select a field in the table first, then click this button to use its selector for crawling."
            )
            return

        # Get the selector from the selected row
        row = selected[0].row()
        selector_item = self.fields_table.item(row, 1)  # Column 1 is selector
        if not selector_item or not selector_item.text():
            QMessageBox.warning(self, "No Selector", "Selected field has no selector.")
            return

        selector = selector_item.text()

        # Add to existing crawl selectors (don't replace)
        existing = self.link_selectors_edit.toPlainText().strip()
        if existing:
            # Check if selector already exists
            existing_list = [s.strip() for s in existing.split('\n') if s.strip()]
            if selector not in existing_list:
                self.link_selectors_edit.setPlainText(existing + '\n' + selector)
        else:
            self.link_selectors_edit.setPlainText(selector)

        self.crawl_enabled.setChecked(True)

        # Expand the crawl group to show the user
        self.crawl_group.setChecked(True)

        # Show confirmation
        field_name = self.fields_table.item(row, 0).text() if self.fields_table.item(row, 0) else "field"
        QMessageBox.information(
            self, "Crawl Selector Added",
            f"Added link selector:\n{selector}\n\nCrawling is now enabled. You can add more selectors (one per line) for pagination."
        )

    def _toggle_select_mode(self, checked: bool):
        """Toggle element selection mode."""
        self._select_mode = checked
        self.select_mode_btn.setText(f"Select Mode: {'ON' if checked else 'OFF'}")

        if checked:
            js = f"""
            var script = document.createElement('script');
            script.src = 'qrc:///qtwebchannel/qwebchannel.js';
            script.onload = function() {{
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    window.bridge = channel.objects.bridge;
                    {self.SELECTOR_JS}
                }});
            }};
            document.head.appendChild(script);
            """
            self.web_view.page().runJavaScript(js)
        else:
            self.web_view.page().runJavaScript("""
                window.parsonicSelectMode = false;
                var overlay = document.getElementById('parsonic-overlay');
                if (overlay) overlay.style.display = 'none';
            """)

    def _on_element_selected(self, css: str, xpath: str, preview: str):
        """Handle element selection from browser."""
        if self._selected_field_row >= 0:
            self.fields_table.item(self._selected_field_row, 1).setText(css)
            self._selected_field_row = -1
            self._on_field_changed()
            self._update_preview_for_selector(css, preview)
        else:
            self._get_element_info(css, lambda info: self._show_field_wizard(css, xpath, preview, info))

    def _get_element_info(self, selector: str, callback):
        """Get detailed element info for smart field name suggestions."""
        js = f"""
        (function() {{
            var el = document.querySelector('{selector.replace("'", "\\'")}');
            if (!el) return {{}};
            return {{
                tag: el.tagName.toLowerCase(),
                classes: Array.from(el.classList),
                id: el.id || '',
                href: el.getAttribute('href') || '',
                src: el.getAttribute('src') || '',
                text: el.textContent.trim().substring(0, 200),
                parentClasses: el.parentElement ? Array.from(el.parentElement.classList) : [],
                nearbyText: el.parentElement ? el.parentElement.textContent.trim().substring(0, 100) : ''
            }};
        }})();
        """
        self.web_view.page().runJavaScript(js, callback)

    def _show_field_wizard(self, css: str, xpath: str, preview: str, element_info: dict):
        """Show the smart field naming wizard."""
        if not element_info:
            element_info = {"text": preview}

        suggestions = suggest_field_name(element_info)

        dialog = FieldWizardDialog(css, element_info, suggestions, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            result = dialog.get_result()

            # Check if user wants to add to crawler instead of as a field
            if result.get("add_to_crawler"):
                # Simplify selector for crawling - remove nth-of-type to match ALL similar links
                import re
                selector = result["selector"]
                # Remove :nth-of-type(N) patterns to make selector generic
                simplified = re.sub(r':nth-of-type\(\d+\)', '', selector)
                # Remove :nth-child(N) patterns too
                simplified = re.sub(r':nth-child\(\d+\)', '', simplified)
                # Clean up any double > or spaces
                simplified = re.sub(r'\s*>\s*>\s*', ' > ', simplified)
                simplified = re.sub(r'\s+', ' ', simplified).strip()

                # Add to existing selectors (don't replace)
                existing = self.link_selectors_edit.toPlainText().strip()
                if existing:
                    existing_list = [s.strip() for s in existing.split('\n') if s.strip()]
                    if simplified not in existing_list:
                        self.link_selectors_edit.setPlainText(existing + '\n' + simplified)
                else:
                    self.link_selectors_edit.setPlainText(simplified)

                self.crawl_enabled.setChecked(True)
                self.crawl_group.setChecked(True)  # Expand the group
                QMessageBox.information(
                    self, "Crawler Link Added",
                    f"Added link selector:\n{simplified}\n\n"
                    "You can add more selectors for pagination (one per line)."
                )
                return

            row = self.fields_table.rowCount()
            self._add_field_row(
                row,
                result["name"],
                result["selector"],
                "css",
                result["attribute"] or ""
            )
            self._on_field_changed()
            self._update_preview_for_selector(css, preview)

    def _add_field(self):
        """Add a new empty field row."""
        row = self.fields_table.rowCount()
        self._add_field_row(row, f"field_{row + 1}", "", "css", "")

    def _add_field_row(self, row: int, name: str, selector: str, sel_type: str, attribute: str):
        """Add a field row to the table."""
        self.fields_table.insertRow(row)

        name_item = QTableWidgetItem(name)
        self.fields_table.setItem(row, 0, name_item)

        selector_item = QTableWidgetItem(selector)
        self.fields_table.setItem(row, 1, selector_item)

        type_combo = QComboBox()
        type_combo.addItems(["css", "xpath"])
        type_combo.setCurrentText(sel_type)
        type_combo.currentIndexChanged.connect(self._on_field_changed)
        self.fields_table.setCellWidget(row, 2, type_combo)

        attr_item = QTableWidgetItem(attribute or "")
        self.fields_table.setItem(row, 3, attr_item)

        # Actions
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(2, 1, 2, 1)
        actions_layout.setSpacing(2)

        pick_btn = QPushButton("Pick")
        pick_btn.setMaximumWidth(35)
        pick_btn.setMaximumHeight(22)
        pick_btn.clicked.connect(lambda: self._start_picking(row))
        actions_layout.addWidget(pick_btn)

        del_btn = QPushButton("X")
        del_btn.setMaximumWidth(22)
        del_btn.setMaximumHeight(22)
        del_btn.setProperty("danger", True)
        del_btn.clicked.connect(lambda: self._delete_field(row))
        actions_layout.addWidget(del_btn)

        self.fields_table.setCellWidget(row, 4, actions_widget)

    def _start_picking(self, row: int):
        """Start picking mode for a specific field."""
        self._selected_field_row = row
        self.select_mode_btn.setChecked(True)
        self._toggle_select_mode(True)
        self.fields_table.selectRow(row)

    def _delete_field(self, row: int):
        """Delete a field row."""
        self.fields_table.removeRow(row)
        self._on_field_changed()

    def _on_field_changed(self):
        """Handle field data changes."""
        self._sync_to_project()
        self.project_changed.emit()

    def _on_settings_changed(self):
        """Handle settings changes."""
        self._sync_to_project()
        self.project_changed.emit()

    def _on_field_selection_changed(self):
        """Handle field row selection change - load fallbacks for selected field."""
        selected_rows = self.fields_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            name_item = self.fields_table.item(row, 0)
            if name_item:
                field_name = name_item.text()
                fallbacks = self._field_fallbacks.get(field_name, [])
                self.fallback_edit.blockSignals(True)
                self.fallback_edit.setPlainText("\n".join(fallbacks))
                self.fallback_edit.blockSignals(False)

    def _on_fallback_changed(self):
        """Handle fallback selector changes."""
        selected_rows = self.fields_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            name_item = self.fields_table.item(row, 0)
            if name_item:
                field_name = name_item.text()
                fallbacks = [
                    line.strip()
                    for line in self.fallback_edit.toPlainText().split('\n')
                    if line.strip()
                ]
                self._field_fallbacks[field_name] = fallbacks
        self._on_field_changed()

    def _ai_analyze_fields(self):
        """Use AI to analyze the page and detect all business fields."""
        # Get current URL
        current_url = self.web_view.url().toString()
        if not current_url or current_url == "about:blank" or current_url.startswith("data:"):
            QMessageBox.warning(
                self, "No Page Loaded",
                "Please load a page first before running AI analysis."
            )
            return

        # Disable select mode if it's on - prevents interference
        if self._select_mode:
            self.select_mode_btn.setChecked(False)
            self._toggle_select_mode(False)

        # Disable button and show progress
        self.ai_analyze_btn.setEnabled(False)
        self.ai_analyze_btn.setText("Revealing...")

        # First, click any "reveal" buttons to expose hidden content
        self._click_reveal_buttons(lambda: self._continue_ai_analysis(current_url))

    def _click_reveal_buttons(self, callback):
        """Click buttons that reveal hidden phone/email content."""
        js = """
        (function() {
            var clicked = 0;

            // Very broad patterns to catch reveal buttons
            var textPatterns = [
                /view\s*email/i,
                /view\s*phone/i,
                /show\s*email/i,
                /show\s*phone/i,
                /reveal/i,
                /click.*view/i,
                /click.*show/i,
                /get\s*(phone|email)/i,
                /see\s*(phone|email)/i,
                /display/i
            ];

            // Click anything that looks like a reveal button
            var allClickable = document.querySelectorAll('button, a, [onclick], [role="button"], .btn, span[class], div[class]');

            allClickable.forEach(function(el) {
                var text = (el.textContent || '').trim().toLowerCase();
                var cls = (el.className || '').toLowerCase();
                var id = (el.id || '').toLowerCase();

                // Check text content
                for (var i = 0; i < textPatterns.length; i++) {
                    if (textPatterns[i].test(text)) {
                        try { el.click(); clicked++; } catch(e) {}
                        return;
                    }
                }

                // Check class/id for email/phone reveal patterns
                if ((cls + id).match(/(email|phone|contact).*(view|show|reveal|btn|button)/i) ||
                    (cls + id).match(/(view|show|reveal).*(email|phone|contact)/i)) {
                    try { el.click(); clicked++; } catch(e) {}
                }
            });

            // Also try clicking any element with specific IDs
            ['email_view', 'phone_view', 'view_email', 'view_phone', 'show_email', 'show_phone'].forEach(function(id) {
                var el = document.getElementById(id);
                if (el) {
                    try { el.click(); clicked++; } catch(e) {}
                }
            });

            // Click elements that contain just "Email" or "Phone" as text (likely buttons)
            document.querySelectorAll('a, button, span, div').forEach(function(el) {
                var text = (el.textContent || '').trim();
                if (text.match(/^(view\s+)?(email|phone|contact)$/i) && el.children.length === 0) {
                    try { el.click(); clicked++; } catch(e) {}
                }
            });

            return clicked;
        })();
        """

        def on_clicked(count):
            # Wait for content to load after clicks
            from PyQt6.QtCore import QTimer
            if count and count > 0:
                QTimer.singleShot(2500, callback)  # Wait 2.5s for content to appear
            else:
                QTimer.singleShot(500, callback)  # Brief wait even if no clicks

        self.web_view.page().runJavaScript(js, on_clicked)

    def _continue_ai_analysis(self, current_url: str):
        """Continue AI analysis after reveal buttons clicked."""
        self.ai_analyze_btn.setText("Analyzing...")
        # Analyze current page only (no deep link following)
        self._start_ai_analysis(current_url, [])

    def _get_page_links(self, current_url: str, callback):
        """Extract same-domain links from the current page."""
        from urllib.parse import urlparse
        base_domain = urlparse(current_url).netloc

        js = f"""
        (function() {{
            var links = [];
            var seen = new Set();
            var baseDomain = '{base_domain}';
            document.querySelectorAll('a[href]').forEach(function(a) {{
                var href = a.href;
                if (href && !seen.has(href)) {{
                    try {{
                        var url = new URL(href);
                        // Same domain links only, no anchors, no javascript
                        if (url.hostname === baseDomain &&
                            !href.includes('#') &&
                            !href.startsWith('javascript:') &&
                            !href.match(/\\.(pdf|jpg|png|gif|css|js)$/i)) {{
                            seen.add(href);
                            links.push(href);
                        }}
                    }} catch(e) {{}}
                }}
            }});
            return links.slice(0, 25);  // Limit to 25 links (supports depth 5)
        }})();
        """

        def on_links_received(links):
            callback(current_url, links or [])

        self.web_view.page().runJavaScript(js, on_links_received)

    def _start_ai_analysis(self, current_url: str, deep_links: list = None):
        """Start the AI analysis worker by extracting elements first."""
        deep_links = deep_links or []
        self.ai_analyze_btn.setText("Extracting...")

        # Extract all text-containing elements with their selectors via JavaScript
        js = """
        (function() {
            var elements = [];
            var seen = new Set();

            function getSelector(el) {
                if (el.id) return '#' + el.id;
                var path = [];
                while (el && el.nodeType === 1) {
                    var selector = el.tagName.toLowerCase();
                    if (el.className && typeof el.className === 'string') {
                        var classes = el.className.trim().split(/\\s+/).filter(c => c && !c.match(/^(ng-|js-|is-|has-|active|open|col-)/));
                        if (classes.length > 0) {
                            selector += '.' + classes.slice(0, 2).join('.');
                        }
                    }
                    path.unshift(selector);
                    if (el.id || path.length > 3) break;
                    el = el.parentElement;
                }
                return path.join(' > ');
            }

            function isInNavOrHeader(el) {
                var parent = el;
                while (parent) {
                    var tag = parent.tagName ? parent.tagName.toLowerCase() : '';
                    var cls = parent.className || '';
                    if (tag === 'nav' || tag === 'header' || tag === 'footer' ||
                        cls.match(/nav|menu|breadcrumb|footer|header|sidebar|dropdown/i)) {
                        return true;
                    }
                    parent = parent.parentElement;
                }
                return false;
            }

            // Priority 1: Headings (h1, h2) - most likely to be company names
            document.querySelectorAll('h1, h2').forEach(function(el) {
                if (isInNavOrHeader(el)) return;
                var text = el.textContent.trim();
                if (!text || text.length > 150 || text.length < 2 || seen.has(text)) return;
                seen.add(text);
                elements.push({
                    selector: getSelector(el),
                    text: text,
                    tag: el.tagName.toLowerCase(),
                    priority: 'heading'
                });
            });

            // Priority 2: Contact info patterns
            document.querySelectorAll('a[href^="tel:"], a[href^="mailto:"]').forEach(function(el) {
                var href = el.getAttribute('href');
                var text = el.textContent.trim() || href.replace(/^(tel:|mailto:)/, '');
                if (seen.has(text)) return;
                seen.add(text);
                elements.push({
                    selector: getSelector(el),
                    text: text,
                    tag: 'a',
                    priority: href.includes('tel:') ? 'phone' : 'email',
                    href: href
                });
            });

            // Priority 3: Elements with semantic classes or attributes
            document.querySelectorAll('[itemprop], [class*="phone"], [class*="email"], [class*="address"], [class*="company"], [class*="business"], [class*="title"]').forEach(function(el) {
                if (isInNavOrHeader(el)) return;
                var text = el.textContent.trim();
                if (!text || text.length > 200 || text.length < 2 || seen.has(text)) return;
                if (el.children.length > 5) return;
                seen.add(text);
                elements.push({
                    selector: getSelector(el),
                    text: text.substring(0, 150),
                    tag: el.tagName.toLowerCase(),
                    priority: 'semantic'
                });
            });

            // Priority 4: Other content elements (not in nav)
            document.querySelectorAll('h3, h4, p, address, span, div').forEach(function(el) {
                if (isInNavOrHeader(el)) return;
                var text = el.textContent.trim();
                if (!text || text.length > 200 || text.length < 3 || seen.has(text)) return;
                if (el.children.length > 3) return;
                // Skip generic short text
                if (text.match(/^(home|about|contact|menu|login|sign|search|more|view|click|here)$/i)) return;
                seen.add(text);
                elements.push({
                    selector: getSelector(el),
                    text: text.substring(0, 150),
                    tag: el.tagName.toLowerCase(),
                    priority: 'content'
                });
            });

            return elements.slice(0, 100);
        })();
        """

        def on_elements_extracted(elements):
            if not elements or len(elements) == 0:
                self.ai_analyze_btn.setEnabled(True)
                self.ai_analyze_btn.setText("AI Analyze")
                QMessageBox.warning(self, "Error", "Could not extract page elements.")
                return

            # Start background worker with elements (always depth 5 = 20 links)
            self._ai_worker = AIAnalyzeWorker(elements, current_url, deep_links, depth=5)
            self._ai_worker.finished.connect(self._on_ai_analysis_complete)
            self._ai_worker.error.connect(self._on_ai_analysis_error)
            self._ai_worker.progress.connect(self._on_ai_analysis_progress)
            self._ai_worker.start()

        self.web_view.page().runJavaScript(js, on_elements_extracted)

    def _on_ai_analysis_progress(self, message: str):
        """Update progress during AI analysis."""
        self.ai_analyze_btn.setText(message[:20] + "...")

    def _on_ai_analysis_complete(self, fields: list):
        """Handle completed AI analysis."""
        self.ai_analyze_btn.setEnabled(True)
        self.ai_analyze_btn.setText("AI Analyze")

        if not fields:
            QMessageBox.information(
                self, "No Fields Found",
                "AI could not detect any business fields on this page.\n\n"
                "Try using Select Mode to manually pick elements."
            )
            return

        # Get existing field names to avoid duplicates
        existing_names = set()
        for row in range(self.fields_table.rowCount()):
            name_item = self.fields_table.item(row, 0)
            if name_item:
                existing_names.add(name_item.text())

        # Add detected fields (don't clear existing - ADD to them)
        added_count = 0
        for field in fields:
            # Skip if we already have this field type
            if field.name in existing_names:
                continue

            row = self.fields_table.rowCount()
            self._add_field_row(
                row,
                field.name,
                field.selector,
                "css",
                field.attribute or ""
            )
            existing_names.add(field.name)
            added_count += 1

        self._on_field_changed()

        # Show summary
        if added_count > 0:
            QMessageBox.information(
                self, "AI Analysis Complete",
                f"Added {added_count} new fields.\n\n"
                "You can now navigate to other pages and run AI Analyze again\n"
                "to add more field types from different pages."
            )
        else:
            QMessageBox.information(
                self, "No New Fields",
                "All detected field types already exist.\n\n"
                "Navigate to a different page type to find more fields."
            )

    def _on_ai_analysis_error(self, error_message: str):
        """Handle AI analysis error."""
        self.ai_analyze_btn.setEnabled(True)
        self.ai_analyze_btn.setText("AI Analyze")

        QMessageBox.warning(
            self, "AI Analysis Failed",
            f"{error_message}\n\n"
            "Make sure Ollama is running:\n"
            "  ollama serve\n\n"
            "And models are installed:\n"
            "  ollama pull qwen2.5-coder:7b"
        )

    def _run_scrape(self):
        """Start the scraper."""
        # Make sure we have URLs
        if not self._url_queue:
            # Use current URL if none queued
            current_url = self.web_view.url().toString()
            if current_url and not current_url.startswith(("about:", "data:")):
                self._url_queue.append(current_url)
                self._update_url_count()

        if not self._url_queue:
            QMessageBox.warning(
                self, "No URLs",
                "Please add URLs to scrape.\n\n"
                "Enter a URL and click 'Add', or just 'Load' a page."
            )
            return

        # Make sure we have fields
        if self.fields_table.rowCount() == 0:
            QMessageBox.warning(
                self, "No Fields",
                "Please define fields to extract.\n\n"
                "Click 'AI Analyze' to auto-detect fields,\n"
                "or use 'Select Mode' to pick elements manually."
            )
            return

        # Sync to project and emit signal
        self._sync_to_project()
        self.run_scrape_requested.emit()

    def _sync_to_project(self):
        """Sync UI values to project model."""
        # URLs - use queue, or current browser URL if queue is empty
        if self._url_queue:
            self.project.target.urls = self._url_queue.copy()
        else:
            # Use current browser URL as starting point
            current_url = self.web_view.url().toString()
            if current_url and current_url.startswith(('http://', 'https://')):
                self.project.target.urls = [current_url]
            else:
                self.project.target.urls = []

        # Site type - always auto-detect
        self.project.target.site_type = SiteType.AUTO

        # Rate limiting
        self.project.rate_limit.min_delay = self.min_delay.value()
        self.project.rate_limit.max_delay = self.max_delay.value()
        self.project.rate_limit.max_concurrent = self.concurrent_spin.value()

        # Crawl settings
        self.project.link_follow.enabled = self.crawl_enabled.isChecked()
        # Parse multiple selectors (one per line)
        selectors_text = self.link_selectors_edit.toPlainText().strip()
        self.project.link_follow.link_selectors = [
            s.strip() for s in selectors_text.split('\n') if s.strip()
        ]
        self.project.link_follow.max_depth = self.max_pages_spin.value()
        self.project.link_follow.same_domain_only = self.same_domain.isChecked()

        # Fields
        fields = []
        for row in range(self.fields_table.rowCount()):
            name_item = self.fields_table.item(row, 0)
            selector_item = self.fields_table.item(row, 1)
            type_combo = self.fields_table.cellWidget(row, 2)
            attr_item = self.fields_table.item(row, 3)

            if name_item and selector_item:
                field_name = name_item.text()
                fallbacks = self._field_fallbacks.get(field_name, [])

                field = SelectorField(
                    name=field_name,
                    selector=selector_item.text(),
                    selector_type=type_combo.currentText() if type_combo else "css",
                    attribute=attr_item.text() if attr_item and attr_item.text() else None,
                    fallback_selectors=fallbacks
                )
                fields.append(field)

        self.project.fields = fields

    def _test_selectors(self):
        """Test all selectors against current page."""
        self.preview_table.setRowCount(0)

        for row in range(self.fields_table.rowCount()):
            name_item = self.fields_table.item(row, 0)
            selector_item = self.fields_table.item(row, 1)
            type_combo = self.fields_table.cellWidget(row, 2)
            attr_item = self.fields_table.item(row, 3)

            if not name_item or not selector_item:
                continue

            name = name_item.text()
            selector = selector_item.text().strip()
            sel_type = type_combo.currentText() if type_combo else "css"
            attribute = attr_item.text() if attr_item else ""

            if not selector:
                self._add_preview_row(name, "[NO SELECTOR]")
                continue

            # Escape selector for JavaScript string
            escaped_selector = selector.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")

            if sel_type == "css":
                js = f"""
                (function() {{
                    try {{
                        var el = document.querySelector('{escaped_selector}');
                        if (!el) return 'NOT FOUND: {escaped_selector[:50]}';
                        return {f'el.getAttribute("{attribute}")' if attribute else 'el.textContent.trim().substring(0, 200)'};
                    }} catch(e) {{
                        return 'SELECTOR ERROR: ' + e.message;
                    }}
                }})();
                """
            else:
                js = f"""
                (function() {{
                    try {{
                        var result = document.evaluate('{escaped_selector}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                        var el = result.singleNodeValue;
                        if (!el) return 'NOT FOUND: {escaped_selector[:50]}';
                        return {f'el.getAttribute("{attribute}")' if attribute else 'el.textContent.trim().substring(0, 200)'};
                    }} catch(e) {{
                        return 'XPATH ERROR: ' + e.message;
                    }}
                }})();
                """

            self.web_view.page().runJavaScript(js, lambda val, n=name: self._add_preview_row(n, val))

    def _add_preview_row(self, name: str, value: str):
        """Add a row to the preview table."""
        row = self.preview_table.rowCount()
        self.preview_table.insertRow(row)
        self.preview_table.setItem(row, 0, QTableWidgetItem(name))
        self.preview_table.setItem(row, 1, QTableWidgetItem(str(value) if value else ""))

    def _update_preview_for_selector(self, selector: str, preview: str):
        """Update preview with a single selector result."""
        row = self.preview_table.rowCount()
        self.preview_table.insertRow(row)
        self.preview_table.setItem(row, 0, QTableWidgetItem("Selected"))
        self.preview_table.setItem(row, 1, QTableWidgetItem(preview))

    def load_project(self, project: ScraperProject):
        """Load project data into UI."""
        self.project = project

        # URLs
        self._url_queue = project.target.urls.copy()
        self.url_list.setRowCount(0)
        for url in self._url_queue:
            row = self.url_list.rowCount()
            self.url_list.insertRow(row)
            self.url_list.setItem(row, 0, QTableWidgetItem(url))
        self._update_url_count()

        # Load first URL in browser
        if self._url_queue:
            self.url_input.setText(self._url_queue[0])
            self.web_view.setUrl(QUrl(self._url_queue[0]))

        # Rate limiting
        self.min_delay.setValue(project.rate_limit.min_delay)
        self.max_delay.setValue(project.rate_limit.max_delay)
        self.concurrent_spin.setValue(project.rate_limit.max_concurrent)

        # Crawl settings
        self.crawl_enabled.setChecked(project.link_follow.enabled)
        # Join list of selectors with newlines
        selectors_str = '\n'.join(project.link_follow.link_selectors) if project.link_follow.link_selectors else ""
        self.link_selectors_edit.setPlainText(selectors_str)
        self.max_pages_spin.setValue(project.link_follow.max_depth)
        self.same_domain.setChecked(project.link_follow.same_domain_only)

        # Fields
        self._field_fallbacks = {}
        self.fields_table.setRowCount(0)
        for field in project.fields:
            row = self.fields_table.rowCount()
            self._add_field_row(
                row,
                field.name,
                field.selector,
                field.selector_type,
                field.attribute or ""
            )
            if field.fallback_selectors:
                self._field_fallbacks[field.name] = field.fallback_selectors
