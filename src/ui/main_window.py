"""Main window for Parsonic web scraper GUI."""

import asyncio
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QMenuBar, QMenu, QStatusBar, QFileDialog, QMessageBox, QLabel,
    QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QKeySequence

from src.models.project import ScraperProject
from src.ui.dialogs.template_picker import TemplatePickerDialog
from src.core.templates import get_template
from src.core.thermal_monitor import (
    get_thermal_monitor, ThermalState, ThermalStatus
)
from src.ui.tabs.scrape_tab import ScrapeTab
from src.ui.tabs.results_tab import ResultsTab
from src.ui.tabs.log_tab import LogTab
from src.ui.tabs.auth_tab import AuthTab
from src.ui.tabs.schedule_tab import ScheduleTab
from src.ui.shortcuts import setup_shortcuts
from src.core.scraper import ScraperOrchestrator
from src.core.scheduler import ScraperScheduler


class MainWindow(QMainWindow):
    """Main application window with tabbed interface."""

    def __init__(self):
        super().__init__()
        self.project = ScraperProject()
        self.project_path: str | None = None
        self.unsaved_changes = False
        self._scraper: Optional[ScraperOrchestrator] = None
        self._scheduler = ScraperScheduler()

        self.settings = QSettings("Parsonic", "Parsonic")

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._setup_shortcuts()
        self._setup_thermal_monitor()
        self._load_geometry()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        self.shortcut_manager = setup_shortcuts(self)

    def _setup_ui(self):
        """Initialize the main UI layout."""
        self.setWindowTitle("Parsonic - Web Scraper")
        self.setMinimumSize(1200, 800)

        # Central widget with main layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)

        # Create tabs
        self.scrape_tab = ScrapeTab(self.project)
        self.auth_tab = AuthTab(self.project)
        self.results_tab = ResultsTab(self.project)
        self.schedule_tab = ScheduleTab(self._scheduler, self.project_path)
        self.log_tab = LogTab()

        self.tabs.addTab(self.scrape_tab, "Scrape")
        self.tabs.addTab(self.auth_tab, "Auth")
        self.tabs.addTab(self.results_tab, "Results")
        self.tabs.addTab(self.schedule_tab, "Schedule")
        self.tabs.addTab(self.log_tab, "Logs")

        # Connect signals
        self.scrape_tab.project_changed.connect(self._on_project_changed)
        self.scrape_tab.run_scrape_requested.connect(self._run_scraper)
        self.auth_tab.project_changed.connect(self._on_project_changed)

    def _setup_menu(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New Project", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        template_action = QAction("New from &Template...", self)
        template_action.setShortcut(QKeySequence("Ctrl+T"))
        template_action.triggered.connect(self._new_from_template)
        file_menu.addAction(template_action)

        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Run menu
        run_menu = menubar.addMenu("&Run")

        test_action = QAction("&Test Single URL", self)
        test_action.setShortcut(QKeySequence("F5"))
        test_action.triggered.connect(self._run_test)
        run_menu.addAction(test_action)

        run_action = QAction("&Run Scraper", self)
        run_action.setShortcut(QKeySequence("F6"))
        run_action.triggered.connect(self._run_scraper)
        run_menu.addAction(run_action)

        run_menu.addSeparator()

        stop_action = QAction("S&top", self)
        stop_action.setShortcut(QKeySequence("Escape"))
        stop_action.triggered.connect(self._stop_scraper)
        run_menu.addAction(stop_action)

        # Export menu
        export_menu = menubar.addMenu("&Export")

        export_csv = QAction("Export to &CSV...", self)
        export_csv.triggered.connect(lambda: self._export("csv"))
        export_menu.addAction(export_csv)

        export_json = QAction("Export to &JSON...", self)
        export_json.triggered.connect(lambda: self._export("json"))
        export_menu.addAction(export_json)

        export_sqlite = QAction("Export to &SQLite...", self)
        export_sqlite.triggered.connect(lambda: self._export("sqlite"))
        export_menu.addAction(export_sqlite)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About Parsonic", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_statusbar(self):
        """Create the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)

        # Thermal status indicator
        self.thermal_label = QLabel("CPU: --°C | GPU: --°C")
        self.thermal_label.setStyleSheet("color: #00ff88; font-size: 11px;")
        self.thermal_label.setMinimumWidth(180)
        self.statusbar.addPermanentWidget(self.thermal_label)

        self.project_label = QLabel("New Project")
        self.statusbar.addPermanentWidget(self.project_label)

    def _setup_thermal_monitor(self):
        """Setup thermal monitoring with UI updates."""
        self._thermal_monitor = get_thermal_monitor()
        self._thermal_monitor.start()

        # Timer to update thermal display (every 3 seconds)
        self._thermal_timer = QTimer(self)
        self._thermal_timer.timeout.connect(self._update_thermal_display)
        self._thermal_timer.start(3000)

        # Initial update
        self._update_thermal_display()

    def _update_thermal_display(self):
        """Update thermal status in status bar."""
        status = self._thermal_monitor.get_status()

        cpu_str = f"{status.cpu_temp:.0f}°C" if status.cpu_temp else "--°C"
        gpu_str = f"{status.gpu_temp:.0f}°C" if status.gpu_temp else "--°C"

        # Color based on state
        if status.state == ThermalState.CRITICAL:
            color = "#ff4444"
            prefix = "CRITICAL "
        elif status.state == ThermalState.DANGER:
            color = "#ff8800"
            prefix = "HOT "
        elif status.state == ThermalState.WARNING:
            color = "#ffaa00"
            prefix = ""
        else:
            color = "#00ff88"
            prefix = ""

        self.thermal_label.setText(f"{prefix}CPU: {cpu_str} | GPU: {gpu_str}")
        self.thermal_label.setStyleSheet(f"color: {color}; font-size: 11px;")

        # Show warning in log if dangerous
        if status.state in (ThermalState.DANGER, ThermalState.CRITICAL):
            if hasattr(self, 'log_tab'):
                self.log_tab.log_warning(f"Thermal {status.state.value}: {status.reason}")

    def is_thermal_safe(self) -> bool:
        """Check if system is thermally safe for AI operations."""
        return self._thermal_monitor.is_safe()

    def _load_geometry(self):
        """Restore window geometry from settings."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)

    def _save_geometry(self):
        """Save window geometry to settings."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())

    def _on_project_changed(self):
        """Handle project modifications."""
        self.unsaved_changes = True
        self._update_title()

    def _update_title(self):
        """Update window title with project name and unsaved indicator."""
        title = f"Parsonic - {self.project.name}"
        if self.unsaved_changes:
            title += " *"
        self.setWindowTitle(title)

    def _new_project(self):
        """Create a new project."""
        if not self._check_unsaved():
            return

        self.project = ScraperProject()
        self.project_path = None
        self.unsaved_changes = False

        self._refresh_all_tabs()
        self._update_title()
        self.project_label.setText("New Project")
        self.log_tab.log_info("New project created")

    def _new_from_template(self):
        """Create a new project from a template."""
        if not self._check_unsaved():
            return

        dialog = TemplatePickerDialog(self)
        if dialog.exec():
            template_id = dialog.get_selected_template_id()
            if template_id:
                try:
                    self.project = get_template(template_id)
                    self.project_path = None
                    self.unsaved_changes = True

                    self._refresh_all_tabs()
                    self._update_title()
                    self.project_label.setText(f"New ({template_id})")
                    self.log_tab.log_info(f"Created project from template: {template_id}")

                    # Switch to Scrape tab to show the pre-populated fields
                    self.tabs.setCurrentWidget(self.scrape_tab)
                except Exception as e:
                    QMessageBox.critical(
                        self, "Template Error",
                        f"Failed to load template:\n{e}"
                    )

    def _open_project(self):
        """Open an existing project."""
        if not self._check_unsaved():
            return

        default_dir = self.settings.value("lastProjectDir", "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            default_dir,
            "Parsonic Projects (*.parsonic.json);;All Files (*)"
        )

        if path:
            try:
                self.project = ScraperProject.load(path)
                self.project_path = path
                self.unsaved_changes = False

                self._refresh_all_tabs()
                self._update_title()
                self.project_label.setText(path.split("/")[-1])
                self.settings.setValue("lastProjectDir", "/".join(path.split("/")[:-1]))
                self.log_tab.log_info(f"Opened project: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open project:\n{e}")

    def _save_project(self):
        """Save the current project."""
        if self.project_path:
            self._do_save(self.project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        """Save the project to a new file."""
        default_dir = self.settings.value("lastProjectDir", "")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            f"{default_dir}/{self.project.name}.parsonic.json",
            "Parsonic Projects (*.parsonic.json);;All Files (*)"
        )

        if path:
            if not path.endswith(".parsonic.json"):
                path += ".parsonic.json"
            self._do_save(path)

    def _do_save(self, path: str):
        """Actually save the project to disk."""
        try:
            # Sync UI values to project before saving
            self.scrape_tab._sync_to_project()
            self.project.save(path)
            self.project_path = path
            self.unsaved_changes = False

            self._update_title()
            self.project_label.setText(path.split("/")[-1])
            self.settings.setValue("lastProjectDir", "/".join(path.split("/")[:-1]))
            self.log_tab.log_info(f"Project saved: {path}")
            self.status_label.setText("Project saved")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")

    def _check_unsaved(self) -> bool:
        """Check for unsaved changes. Returns True if OK to proceed."""
        if not self.unsaved_changes:
            return True

        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Do you want to save before continuing?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )

        if result == QMessageBox.StandardButton.Save:
            self._save_project()
            return True
        elif result == QMessageBox.StandardButton.Discard:
            return True
        else:
            return False

    def _refresh_all_tabs(self):
        """Refresh all tabs with current project data."""
        self.scrape_tab.load_project(self.project)
        self.auth_tab.load_project(self.project)
        # Don't clear results - they persist between sessions

    def _run_test(self):
        """Run scraper on a single URL for testing."""
        if not self.project.target.urls:
            QMessageBox.warning(self, "No URL", "Please add at least one URL to test.")
            return

        if not self.project.fields:
            QMessageBox.warning(self, "No Fields", "Please define at least one extraction field.")
            return

        self.tabs.setCurrentWidget(self.log_tab)
        self.status_label.setText("Running test...")

        # Create scraper and run test
        self._scraper = ScraperOrchestrator(self.project)
        self._scraper.log.connect(self._on_scraper_log)

        async def run_test():
            try:
                result = await self._scraper.test_single_url()
                if result.success:
                    self.log_tab.log_info(f"Test completed successfully")
                    # Show results
                    self.results_tab.set_columns([f.name for f in self.project.fields])
                    self.results_tab.add_result(result.url, result.data)
                    self.tabs.setCurrentWidget(self.results_tab)
                else:
                    self.log_tab.log_error(f"Test failed: {result.error}")
                self.status_label.setText("Ready")
            except Exception as e:
                self.log_tab.log_error(f"Test error: {e}")
                self.status_label.setText("Error")
            finally:
                await self._scraper.close()

        asyncio.ensure_future(run_test())

    def _run_scraper(self):
        """Run the full scraper."""
        if not self.project.target.urls:
            QMessageBox.warning(self, "No URLs", "Please add URLs to scrape.")
            return

        if not self.project.fields:
            QMessageBox.warning(self, "No Fields", "Please define extraction fields.")
            return

        self.tabs.setCurrentWidget(self.log_tab)
        self.status_label.setText("Scraping...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.project.target.urls))
        self.progress_bar.setValue(0)

        # Set columns (don't clear - results persist between scans)
        self.results_tab.set_columns([f.name for f in self.project.fields])

        # Create scraper
        self._scraper = ScraperOrchestrator(self.project)
        self._scraper.log.connect(self._on_scraper_log)
        self._scraper.progress.connect(self._on_scraper_progress)
        self._scraper.completed.connect(self._on_scraper_completed)
        self._scraper.robots_warning.connect(self._on_robots_warning)
        self._scraper.paused.connect(self._on_scraper_paused)

        async def run_scraper():
            try:
                await self._scraper.run()
            except Exception as e:
                self.log_tab.log_error(f"Scraper error: {e}")
            finally:
                await self._scraper.close()

        asyncio.ensure_future(run_scraper())

    def _stop_scraper(self):
        """Stop the running scraper."""
        if self._scraper and self._scraper.is_running:
            self._scraper.stop()
            self.log_tab.log_warning("Scraper stopped by user")
            self.status_label.setText("Stopped")
            self.progress_bar.setVisible(False)

    def _on_scraper_log(self, level: str, message: str):
        """Handle log messages from scraper."""
        if level == "info":
            self.log_tab.log_info(message)
        elif level == "warning":
            self.log_tab.log_warning(message)
        elif level == "error":
            self.log_tab.log_error(message)
        else:
            self.log_tab.log_debug(message)

    def _on_scraper_progress(self, current: int, total: int, result):
        """Handle progress updates from scraper."""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Scraping {current}/{total}...")

        if result.success:
            self.results_tab.add_result(result.url, result.data)

    def _on_scraper_completed(self, results: list):
        """Handle scraper completion."""
        success_count = sum(1 for r in results if r.success)
        self.status_label.setText(f"Completed: {success_count}/{len(results)} successful")
        self.progress_bar.setVisible(False)
        self.tabs.setCurrentWidget(self.results_tab)

    def _on_robots_warning(self, warning):
        """Handle robots.txt warnings."""
        self.log_tab.log_warning(f"robots.txt: {warning.message}")

    def _on_scraper_paused(self, reason: str, context):
        """Handle scraper pause for user decision."""
        result = QMessageBox.question(
            self,
            "Scraper Paused",
            f"Error encountered: {reason}\n\nDo you want to continue?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Abort
        )

        if result == QMessageBox.StandardButton.Yes:
            self._scraper.resume()
        elif result == QMessageBox.StandardButton.No:
            self._scraper.skip_current()
        else:
            self._scraper.stop()

    def _export(self, format: str):
        """Export results to specified format."""
        self.results_tab._export(format)
        self.log_tab.log_info(f"Exported to {format.upper()}")

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Parsonic",
            "<h2>Parsonic</h2>"
            "<p>A powerful, open-source web scraper with visual selector builder.</p>"
            "<p>Version 1.0.0</p>"
            "<p>Built with PyQt6, Playwright, and Scrapling.</p>"
        )

    def closeEvent(self, event):
        """Handle window close event."""
        if self._check_unsaved():
            self._save_geometry()
            # Stop thermal monitoring
            if hasattr(self, '_thermal_monitor'):
                self._thermal_monitor.stop()
            if hasattr(self, '_thermal_timer'):
                self._thermal_timer.stop()
            event.accept()
        else:
            event.ignore()
