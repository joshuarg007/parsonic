"""Authentication configuration tab for Parsonic."""

import asyncio
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QTextEdit, QPushButton, QLabel, QComboBox,
    QStackedWidget, QFileDialog, QMessageBox, QCheckBox
)
from PyQt6.QtCore import pyqtSignal

from src.models.project import ScraperProject, AuthType, AuthConfig
from src.core.scraper import ScraperOrchestrator


class AuthTab(QWidget):
    """Tab for configuring authentication methods."""

    project_changed = pyqtSignal()

    def __init__(self, project: ScraperProject):
        super().__init__()
        self.project = project
        self._setup_ui()

    def _setup_ui(self):
        """Build the authentication configuration UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Auth method selector
        method_group = QGroupBox("Authentication Method")
        method_layout = QFormLayout(method_group)

        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "None",
            "Cookies",
            "Bearer Token",
            "Basic Auth",
            "Form Login",
            "Browser Session"
        ])
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addRow("Method:", self.method_combo)

        layout.addWidget(method_group)

        # Stacked widget for different auth configurations
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Page 0: None
        none_page = QWidget()
        none_layout = QVBoxLayout(none_page)
        none_layout.addWidget(QLabel("No authentication configured."))
        none_layout.addStretch()
        self.stack.addWidget(none_page)

        # Page 1: Cookies
        cookies_page = QWidget()
        cookies_layout = QVBoxLayout(cookies_page)

        cookies_group = QGroupBox("Cookie Configuration")
        cookies_form = QVBoxLayout(cookies_group)

        self.cookies_edit = QTextEdit()
        self.cookies_edit.setPlaceholderText(
            "Paste cookies here in one of these formats:\n\n"
            "1. Netscape format (from browser export):\n"
            "   .domain.com  TRUE  /  FALSE  0  name  value\n\n"
            "2. JSON format:\n"
            "   [{\"name\": \"session\", \"value\": \"abc123\", \"domain\": \".example.com\"}]\n\n"
            "3. Simple format (one per line):\n"
            "   name=value; name2=value2"
        )
        self.cookies_edit.textChanged.connect(self._on_change)
        cookies_form.addWidget(self.cookies_edit)

        import_cookies_btn = QPushButton("Import from File")
        import_cookies_btn.setProperty("secondary", True)
        import_cookies_btn.clicked.connect(self._import_cookies)
        cookies_form.addWidget(import_cookies_btn)

        cookies_layout.addWidget(cookies_group)
        cookies_layout.addStretch()
        self.stack.addWidget(cookies_page)

        # Page 2: Bearer Token
        bearer_page = QWidget()
        bearer_layout = QVBoxLayout(bearer_page)

        bearer_group = QGroupBox("Bearer Token")
        bearer_form = QFormLayout(bearer_group)

        self.bearer_input = QLineEdit()
        self.bearer_input.setPlaceholderText("Enter bearer token (without 'Bearer ' prefix)")
        self.bearer_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.bearer_input.textChanged.connect(self._on_change)
        bearer_form.addRow("Token:", self.bearer_input)

        self.bearer_show = QCheckBox("Show token")
        self.bearer_show.toggled.connect(
            lambda checked: self.bearer_input.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        bearer_form.addRow("", self.bearer_show)

        bearer_layout.addWidget(bearer_group)
        bearer_layout.addStretch()
        self.stack.addWidget(bearer_page)

        # Page 3: Basic Auth
        basic_page = QWidget()
        basic_layout = QVBoxLayout(basic_page)

        basic_group = QGroupBox("Basic Authentication")
        basic_form = QFormLayout(basic_group)

        self.basic_user = QLineEdit()
        self.basic_user.setPlaceholderText("Username")
        self.basic_user.textChanged.connect(self._on_change)
        basic_form.addRow("Username:", self.basic_user)

        self.basic_pass = QLineEdit()
        self.basic_pass.setPlaceholderText("Password")
        self.basic_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.basic_pass.textChanged.connect(self._on_change)
        basic_form.addRow("Password:", self.basic_pass)

        basic_layout.addWidget(basic_group)
        basic_layout.addStretch()
        self.stack.addWidget(basic_page)

        # Page 4: Form Login
        form_page = QWidget()
        form_layout = QVBoxLayout(form_page)

        form_group = QGroupBox("Form Login Configuration")
        form_form = QFormLayout(form_group)

        self.login_url = QLineEdit()
        self.login_url.setPlaceholderText("https://example.com/login")
        self.login_url.textChanged.connect(self._on_change)
        form_form.addRow("Login URL:", self.login_url)

        self.username_selector = QLineEdit()
        self.username_selector.setPlaceholderText("#username or input[name='email']")
        self.username_selector.textChanged.connect(self._on_change)
        form_form.addRow("Username Selector:", self.username_selector)

        self.password_selector = QLineEdit()
        self.password_selector.setPlaceholderText("#password or input[type='password']")
        self.password_selector.textChanged.connect(self._on_change)
        form_form.addRow("Password Selector:", self.password_selector)

        self.submit_selector = QLineEdit()
        self.submit_selector.setPlaceholderText("button[type='submit'] or #login-btn")
        self.submit_selector.textChanged.connect(self._on_change)
        form_form.addRow("Submit Selector:", self.submit_selector)

        self.success_selector = QLineEdit()
        self.success_selector.setPlaceholderText("Optional: selector visible after successful login")
        self.success_selector.textChanged.connect(self._on_change)
        form_form.addRow("Success Indicator:", self.success_selector)

        form_layout.addWidget(form_group)

        creds_group = QGroupBox("Credentials")
        creds_form = QFormLayout(creds_group)

        self.form_user = QLineEdit()
        self.form_user.setPlaceholderText("Your username or email")
        self.form_user.textChanged.connect(self._on_change)
        creds_form.addRow("Username:", self.form_user)

        self.form_pass = QLineEdit()
        self.form_pass.setPlaceholderText("Your password")
        self.form_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.form_pass.textChanged.connect(self._on_change)
        creds_form.addRow("Password:", self.form_pass)

        form_layout.addWidget(creds_group)

        # Test login button
        test_login_btn = QPushButton("Test Login")
        test_login_btn.clicked.connect(self._test_login)
        form_layout.addWidget(test_login_btn)

        form_layout.addStretch()
        self.stack.addWidget(form_page)

        # Page 5: Browser Session
        session_page = QWidget()
        session_layout = QVBoxLayout(session_page)

        session_group = QGroupBox("Browser Session")
        session_form = QVBoxLayout(session_group)

        session_form.addWidget(QLabel(
            "Record a browser session by logging in manually.\n"
            "The session (cookies, localStorage) will be saved and reused."
        ))

        self.session_path = QLineEdit()
        self.session_path.setPlaceholderText("Session file path")
        self.session_path.setReadOnly(True)
        session_form.addWidget(self.session_path)

        session_buttons = QHBoxLayout()

        record_btn = QPushButton("Record New Session")
        record_btn.clicked.connect(self._record_session)
        session_buttons.addWidget(record_btn)

        load_btn = QPushButton("Load Session File")
        load_btn.setProperty("secondary", True)
        load_btn.clicked.connect(self._load_session)
        session_buttons.addWidget(load_btn)

        session_form.addLayout(session_buttons)
        session_layout.addWidget(session_group)
        session_layout.addStretch()
        self.stack.addWidget(session_page)

        layout.addStretch()

    def _on_method_changed(self, index: int):
        """Handle auth method change."""
        self.stack.setCurrentIndex(index)
        self._on_change()

    def _on_change(self):
        """Emit signal when any field changes."""
        self._sync_to_project()
        self.project_changed.emit()

    def _sync_to_project(self):
        """Sync UI values to project model."""
        method_map = {
            0: AuthType.NONE,
            1: AuthType.COOKIES,
            2: AuthType.BEARER,
            3: AuthType.BASIC,
            4: AuthType.FORM,
            5: AuthType.SESSION
        }

        self.project.auth.type = method_map.get(self.method_combo.currentIndex(), AuthType.NONE)

        # Sync based on current method
        if self.project.auth.type == AuthType.COOKIES:
            self.project.auth.cookies = self.cookies_edit.toPlainText()
        elif self.project.auth.type == AuthType.BEARER:
            self.project.auth.bearer_token = self.bearer_input.text()
        elif self.project.auth.type == AuthType.BASIC:
            self.project.auth.username = self.basic_user.text()
            self.project.auth.password = self.basic_pass.text()
        elif self.project.auth.type == AuthType.FORM:
            self.project.auth.login_url = self.login_url.text()
            self.project.auth.login_selector = json.dumps({
                "username": self.username_selector.text(),
                "password": self.password_selector.text(),
                "submit": self.submit_selector.text(),
                "success": self.success_selector.text()
            })
            self.project.auth.username = self.form_user.text()
            self.project.auth.password = self.form_pass.text()

    def _import_cookies(self):
        """Import cookies from a file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Cookies",
            "",
            "Cookie Files (*.txt *.json);;All Files (*)"
        )

        if path:
            try:
                with open(path, 'r') as f:
                    content = f.read()
                self.cookies_edit.setPlainText(content)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import cookies:\n{e}")

    def _test_login(self):
        """Test form login configuration."""
        if not all([
            self.login_url.text(),
            self.username_selector.text(),
            self.password_selector.text(),
            self.submit_selector.text(),
            self.form_user.text(),
            self.form_pass.text()
        ]):
            QMessageBox.warning(self, "Missing Fields", "Please fill in all login fields.")
            return

        orchestrator = ScraperOrchestrator(self.project)

        async def do_login():
            try:
                success = await orchestrator.perform_login(
                    login_url=self.login_url.text(),
                    username_selector=self.username_selector.text(),
                    password_selector=self.password_selector.text(),
                    submit_selector=self.submit_selector.text(),
                    username=self.form_user.text(),
                    password=self.form_pass.text(),
                    success_indicator=self.success_selector.text() or None
                )
                return success
            finally:
                await orchestrator.close()

        def on_result(success):
            if success:
                QMessageBox.information(self, "Success", "Login successful!")
            else:
                QMessageBox.warning(self, "Failed", "Login failed. Check your selectors and credentials.")

        def run_login():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're in an async context (qasync), use ensure_future
                future = asyncio.ensure_future(do_login())
                future.add_done_callback(lambda f: on_result(f.result() if not f.exception() else False))
            else:
                # No running loop, run synchronously
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(do_login())
                    on_result(result)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Login test failed: {e}")
                finally:
                    if loop:
                        loop.close()

        run_login()

    def _record_session(self):
        """Open browser for manual login recording."""
        QMessageBox.information(
            self,
            "Record Session",
            "A browser window will open. Please:\n\n"
            "1. Navigate to the login page\n"
            "2. Log in manually\n"
            "3. Close the browser when done\n\n"
            "Your session will be saved automatically."
        )

        # For now, show file save dialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Session",
            "session.json",
            "Session Files (*.json)"
        )

        if path:
            self.session_path.setText(path)
            # TODO: Actually record session with visible browser
            QMessageBox.information(
                self,
                "Session Recording",
                "Session recording with visible browser is not yet implemented.\n\n"
                "For now, please use the Form Login method or import cookies manually."
            )

    def _load_session(self):
        """Load existing session file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Session",
            "",
            "Session Files (*.json);;All Files (*)"
        )

        if path:
            if Path(path).exists():
                self.session_path.setText(path)
                self._on_change()
            else:
                QMessageBox.warning(self, "Not Found", "Session file not found.")

    def load_project(self, project: ScraperProject):
        """Load project data into UI."""
        self.project = project

        # Set method
        type_map = {
            AuthType.NONE: 0,
            AuthType.COOKIES: 1,
            AuthType.BEARER: 2,
            AuthType.BASIC: 3,
            AuthType.FORM: 4,
            AuthType.SESSION: 5
        }
        self.method_combo.setCurrentIndex(type_map.get(project.auth.type, 0))

        # Load values based on type
        if project.auth.cookies:
            self.cookies_edit.setPlainText(project.auth.cookies)

        if project.auth.bearer_token:
            self.bearer_input.setText(project.auth.bearer_token)

        if project.auth.username:
            self.basic_user.setText(project.auth.username)
            self.form_user.setText(project.auth.username)

        if project.auth.password:
            self.basic_pass.setText(project.auth.password)
            self.form_pass.setText(project.auth.password)

        if project.auth.login_url:
            self.login_url.setText(project.auth.login_url)

        if project.auth.login_selector:
            try:
                selectors = json.loads(project.auth.login_selector)
                self.username_selector.setText(selectors.get("username", ""))
                self.password_selector.setText(selectors.get("password", ""))
                self.submit_selector.setText(selectors.get("submit", ""))
                self.success_selector.setText(selectors.get("success", ""))
            except Exception:
                pass
