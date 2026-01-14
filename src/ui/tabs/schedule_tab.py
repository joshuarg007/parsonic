"""Schedule management tab for Parsonic."""

from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QSpinBox, QDateTimeEdit, QCheckBox,
    QMessageBox, QFileDialog, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QDateTime

from src.core.scheduler import ScraperScheduler, ScheduledJob


class AddScheduleDialog(QDialog):
    """Dialog for adding a new scheduled job."""

    def __init__(self, parent=None, current_project_path: str = None):
        super().__init__(parent)
        self.current_project_path = current_project_path
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Add Scheduled Job")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Project selection
        project_group = QGroupBox("Project")
        project_layout = QHBoxLayout(project_group)

        self.project_path = QLineEdit()
        self.project_path.setPlaceholderText("Select project file...")
        if self.current_project_path:
            self.project_path.setText(self.current_project_path)
        project_layout.addWidget(self.project_path)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_project)
        project_layout.addWidget(browse_btn)

        layout.addWidget(project_group)

        # Schedule type
        schedule_group = QGroupBox("Schedule")
        schedule_layout = QFormLayout(schedule_group)

        self.schedule_type = QComboBox()
        self.schedule_type.addItems(["Run Once", "Interval", "Cron (Advanced)"])
        self.schedule_type.currentIndexChanged.connect(self._on_type_changed)
        schedule_layout.addRow("Type:", self.schedule_type)

        # Once options
        self.once_widget = QWidget()
        once_layout = QFormLayout(self.once_widget)
        once_layout.setContentsMargins(0, 0, 0, 0)

        self.run_date = QDateTimeEdit()
        self.run_date.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.run_date.setCalendarPopup(True)
        once_layout.addRow("Run at:", self.run_date)

        schedule_layout.addRow(self.once_widget)

        # Interval options
        self.interval_widget = QWidget()
        interval_layout = QFormLayout(self.interval_widget)
        interval_layout.setContentsMargins(0, 0, 0, 0)

        interval_row = QHBoxLayout()
        self.interval_value = QSpinBox()
        self.interval_value.setRange(1, 999)
        self.interval_value.setValue(1)
        interval_row.addWidget(self.interval_value)

        self.interval_unit = QComboBox()
        self.interval_unit.addItems(["Minutes", "Hours", "Days", "Weeks"])
        self.interval_unit.setCurrentIndex(1)  # Hours
        interval_row.addWidget(self.interval_unit)

        interval_layout.addRow("Every:", interval_row)
        self.interval_widget.setVisible(False)

        schedule_layout.addRow(self.interval_widget)

        # Cron options
        self.cron_widget = QWidget()
        cron_layout = QFormLayout(self.cron_widget)
        cron_layout.setContentsMargins(0, 0, 0, 0)

        self.cron_minute = QLineEdit("0")
        self.cron_minute.setPlaceholderText("0-59 or *")
        cron_layout.addRow("Minute:", self.cron_minute)

        self.cron_hour = QLineEdit("*")
        self.cron_hour.setPlaceholderText("0-23 or *")
        cron_layout.addRow("Hour:", self.cron_hour)

        self.cron_day = QLineEdit("*")
        self.cron_day.setPlaceholderText("1-31 or *")
        cron_layout.addRow("Day:", self.cron_day)

        self.cron_month = QLineEdit("*")
        self.cron_month.setPlaceholderText("1-12 or *")
        cron_layout.addRow("Month:", self.cron_month)

        self.cron_dow = QLineEdit("*")
        self.cron_dow.setPlaceholderText("0-6 (Mon-Sun) or *")
        cron_layout.addRow("Day of Week:", self.cron_dow)

        cron_layout.addRow(QLabel("Examples: '0' = at 0, '*/5' = every 5, '1,15' = at 1 and 15"))
        self.cron_widget.setVisible(False)

        schedule_layout.addRow(self.cron_widget)

        layout.addWidget(schedule_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Project",
            "",
            "Parsonic Projects (*.parsonic.json);;All Files (*)"
        )
        if path:
            self.project_path.setText(path)

    def _on_type_changed(self, index: int):
        self.once_widget.setVisible(index == 0)
        self.interval_widget.setVisible(index == 1)
        self.cron_widget.setVisible(index == 2)

    def get_config(self) -> dict:
        """Get the schedule configuration."""
        project_path = self.project_path.text()
        schedule_type = ["once", "interval", "cron"][self.schedule_type.currentIndex()]

        if schedule_type == "once":
            config = {
                "run_date": self.run_date.dateTime().toPyDateTime().isoformat()
            }
        elif schedule_type == "interval":
            value = self.interval_value.value()
            unit = self.interval_unit.currentText().lower()

            config = {}
            if unit == "minutes":
                config["minutes"] = value
            elif unit == "hours":
                config["hours"] = value
            elif unit == "days":
                config["days"] = value
            elif unit == "weeks":
                config["weeks"] = value
        else:  # cron
            config = {
                "minute": self.cron_minute.text() or "*",
                "hour": self.cron_hour.text() or "*",
                "day": self.cron_day.text() or "*",
                "month": self.cron_month.text() or "*",
                "day_of_week": self.cron_dow.text() or "*"
            }

        return {
            "project_path": project_path,
            "schedule_type": schedule_type,
            "config": config
        }


class ScheduleTab(QWidget):
    """Tab for managing scheduled scraping jobs."""

    def __init__(self, scheduler: ScraperScheduler, current_project_path: str = None):
        super().__init__()
        self.scheduler = scheduler
        self.current_project_path = current_project_path
        self._setup_ui()
        self._connect_signals()
        self._refresh_jobs()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()

        header.addWidget(QLabel("Scheduled Jobs"))
        header.addStretch()

        self.add_btn = QPushButton("+ Add Schedule")
        self.add_btn.clicked.connect(self._add_schedule)
        header.addWidget(self.add_btn)

        layout.addLayout(header)

        # Jobs table
        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(7)
        self.jobs_table.setHorizontalHeaderLabels([
            "Project", "Schedule", "Next Run", "Last Run", "Status", "Runs", "Actions"
        ])

        header_view = self.jobs_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)

        self.jobs_table.setColumnWidth(1, 120)
        self.jobs_table.setColumnWidth(2, 140)
        self.jobs_table.setColumnWidth(3, 140)
        self.jobs_table.setColumnWidth(4, 120)
        self.jobs_table.setColumnWidth(5, 50)
        self.jobs_table.setColumnWidth(6, 150)

        self.jobs_table.setAlternatingRowColors(True)
        self.jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        layout.addWidget(self.jobs_table)

        # Info
        info_layout = QHBoxLayout()

        self.status_label = QLabel("Scheduler: Stopped")
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()

        self.start_btn = QPushButton("Start Scheduler")
        self.start_btn.clicked.connect(self._toggle_scheduler)
        info_layout.addWidget(self.start_btn)

        layout.addLayout(info_layout)

    def _connect_signals(self):
        self.scheduler.job_started.connect(self._on_job_started)
        self.scheduler.job_completed.connect(self._on_job_completed)
        self.scheduler.job_error.connect(self._on_job_error)
        self.scheduler.job_added.connect(self._refresh_jobs)
        self.scheduler.job_removed.connect(self._refresh_jobs)

    def _refresh_jobs(self):
        """Refresh the jobs table."""
        self.jobs_table.setRowCount(0)

        for job in self.scheduler.get_jobs():
            self._add_job_row(job)

    def _add_job_row(self, job: ScheduledJob):
        row = self.jobs_table.rowCount()
        self.jobs_table.insertRow(row)

        # Project name
        project_name = job.project_path.split("/")[-1] if "/" in job.project_path else job.project_path
        self.jobs_table.setItem(row, 0, QTableWidgetItem(project_name))

        # Schedule description
        schedule_desc = self._format_schedule(job.schedule_type, job.schedule_config)
        self.jobs_table.setItem(row, 1, QTableWidgetItem(schedule_desc))

        # Next run
        next_run = self.scheduler.get_next_run_time(job.id)
        next_str = next_run.strftime("%Y-%m-%d %H:%M") if next_run else "N/A"
        self.jobs_table.setItem(row, 2, QTableWidgetItem(next_str))

        # Last run
        last_str = job.last_run.strftime("%Y-%m-%d %H:%M") if job.last_run else "Never"
        self.jobs_table.setItem(row, 3, QTableWidgetItem(last_str))

        # Status
        status_item = QTableWidgetItem(job.last_status or "Pending")
        if job.last_status and "Error" in job.last_status:
            status_item.setForeground(Qt.GlobalColor.red)
        elif job.last_status and "Success" in job.last_status:
            status_item.setForeground(Qt.GlobalColor.green)
        self.jobs_table.setItem(row, 4, status_item)

        # Run count
        self.jobs_table.setItem(row, 5, QTableWidgetItem(str(job.run_count)))

        # Actions
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(4, 2, 4, 2)
        actions_layout.setSpacing(4)

        run_btn = QPushButton("Run")
        run_btn.setMaximumWidth(40)
        run_btn.clicked.connect(lambda _, jid=job.id: self._run_now(jid))
        actions_layout.addWidget(run_btn)

        toggle_btn = QPushButton("Off" if job.enabled else "On")
        toggle_btn.setMaximumWidth(35)
        toggle_btn.setProperty("secondary", True)
        toggle_btn.clicked.connect(lambda _, jid=job.id: self._toggle_job(jid))
        actions_layout.addWidget(toggle_btn)

        del_btn = QPushButton("X")
        del_btn.setMaximumWidth(25)
        del_btn.setProperty("danger", True)
        del_btn.clicked.connect(lambda _, jid=job.id: self._delete_job(jid))
        actions_layout.addWidget(del_btn)

        self.jobs_table.setCellWidget(row, 6, actions_widget)

    def _format_schedule(self, schedule_type: str, config: dict) -> str:
        """Format schedule config for display."""
        if schedule_type == "once":
            return "Once"
        elif schedule_type == "interval":
            if config.get("minutes"):
                return f"Every {config['minutes']}m"
            elif config.get("hours"):
                return f"Every {config['hours']}h"
            elif config.get("days"):
                return f"Every {config['days']}d"
            elif config.get("weeks"):
                return f"Every {config['weeks']}w"
        elif schedule_type == "cron":
            return f"Cron"
        return "Unknown"

    def _add_schedule(self):
        dialog = AddScheduleDialog(self, self.current_project_path)
        if dialog.exec():
            config = dialog.get_config()
            if not config["project_path"]:
                QMessageBox.warning(self, "Error", "Please select a project file.")
                return

            self.scheduler.add_job(
                project_path=config["project_path"],
                schedule_type=config["schedule_type"],
                schedule_config=config["config"]
            )

    def _run_now(self, job_id: str):
        self.scheduler.run_job_now(job_id)

    def _toggle_job(self, job_id: str):
        job = self.scheduler.get_job(job_id)
        if job:
            if job.enabled:
                self.scheduler.disable_job(job_id)
            else:
                self.scheduler.enable_job(job_id)
            self._refresh_jobs()

    def _delete_job(self, job_id: str):
        result = QMessageBox.question(
            self,
            "Delete Job",
            "Are you sure you want to delete this scheduled job?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result == QMessageBox.StandardButton.Yes:
            self.scheduler.remove_job(job_id)

    def _toggle_scheduler(self):
        if self.scheduler.is_running:
            self.scheduler.stop()
            self.start_btn.setText("Start Scheduler")
            self.status_label.setText("Scheduler: Stopped")
        else:
            self.scheduler.start()
            self.start_btn.setText("Stop Scheduler")
            self.status_label.setText("Scheduler: Running")

    def _on_job_started(self, job_id: str):
        self._refresh_jobs()

    def _on_job_completed(self, job_id: str, success: bool, count: int):
        self._refresh_jobs()

    def _on_job_error(self, job_id: str, error: str):
        self._refresh_jobs()

    def set_current_project(self, path: str):
        """Update current project path."""
        self.current_project_path = path
