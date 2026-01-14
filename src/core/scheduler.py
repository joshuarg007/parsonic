"""Job scheduler for Parsonic using APScheduler."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from PyQt6.QtCore import QObject, pyqtSignal

from src.models.project import ScraperProject
from src.core.scraper import ScraperOrchestrator


@dataclass
class ScheduledJob:
    """Represents a scheduled scraping job."""
    id: str
    project_path: str
    schedule_type: str  # once, interval, cron
    schedule_config: dict
    enabled: bool = True
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    run_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)


class ScraperScheduler(QObject):
    """Manages scheduled scraping jobs."""

    # Signals
    job_started = pyqtSignal(str)  # job_id
    job_completed = pyqtSignal(str, bool, int)  # job_id, success, result_count
    job_error = pyqtSignal(str, str)  # job_id, error message
    job_added = pyqtSignal(str)  # job_id
    job_removed = pyqtSignal(str)  # job_id

    def __init__(self, data_dir: str = "data"):
        super().__init__()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Job store
        db_path = self.data_dir / "scheduler.db"
        jobstores = {
            'default': SQLAlchemyJobStore(url=f'sqlite:///{db_path}')
        }

        executors = {
            'default': AsyncIOExecutor()
        }

        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 60
        }

        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults
        )

        self._jobs: dict[str, ScheduledJob] = {}
        self._load_jobs()

    def _load_jobs(self):
        """Load job metadata from disk."""
        jobs_file = self.data_dir / "scheduled_jobs.json"
        if jobs_file.exists():
            try:
                with open(jobs_file, 'r') as f:
                    data = json.load(f)
                    for job_data in data:
                        job = ScheduledJob(
                            id=job_data['id'],
                            project_path=job_data['project_path'],
                            schedule_type=job_data['schedule_type'],
                            schedule_config=job_data['schedule_config'],
                            enabled=job_data.get('enabled', True),
                            run_count=job_data.get('run_count', 0)
                        )
                        if job_data.get('last_run'):
                            job.last_run = datetime.fromisoformat(job_data['last_run'])
                        job.last_status = job_data.get('last_status')
                        self._jobs[job.id] = job
            except Exception as e:
                print(f"Error loading scheduled jobs: {e}")

    def _save_jobs(self):
        """Save job metadata to disk."""
        jobs_file = self.data_dir / "scheduled_jobs.json"
        data = []
        for job in self._jobs.values():
            data.append({
                'id': job.id,
                'project_path': job.project_path,
                'schedule_type': job.schedule_type,
                'schedule_config': job.schedule_config,
                'enabled': job.enabled,
                'last_run': job.last_run.isoformat() if job.last_run else None,
                'last_status': job.last_status,
                'run_count': job.run_count
            })
        with open(jobs_file, 'w') as f:
            json.dump(data, f, indent=2)

    def start(self):
        """Start the scheduler."""
        if not self._scheduler.running:
            self._scheduler.start()

            # Re-add enabled jobs
            for job in self._jobs.values():
                if job.enabled:
                    self._add_job_to_scheduler(job)

    def stop(self):
        """Stop the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._scheduler.running

    def add_job(
        self,
        project_path: str,
        schedule_type: str,
        schedule_config: dict,
        job_id: str = None
    ) -> str:
        """Add a new scheduled job."""
        if job_id is None:
            job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        job = ScheduledJob(
            id=job_id,
            project_path=project_path,
            schedule_type=schedule_type,
            schedule_config=schedule_config
        )

        self._jobs[job_id] = job
        self._save_jobs()

        if self._scheduler.running:
            self._add_job_to_scheduler(job)

        self.job_added.emit(job_id)
        return job_id

    def _add_job_to_scheduler(self, job: ScheduledJob):
        """Add job to APScheduler."""
        trigger = self._create_trigger(job.schedule_type, job.schedule_config)
        if trigger:
            self._scheduler.add_job(
                self._run_job,
                trigger=trigger,
                id=job.id,
                args=[job.id],
                replace_existing=True
            )

    def _create_trigger(self, schedule_type: str, config: dict):
        """Create APScheduler trigger from config."""
        if schedule_type == "once":
            run_date = config.get("run_date")
            if run_date:
                return DateTrigger(run_date=datetime.fromisoformat(run_date))

        elif schedule_type == "interval":
            return IntervalTrigger(
                weeks=config.get("weeks", 0),
                days=config.get("days", 0),
                hours=config.get("hours", 0),
                minutes=config.get("minutes", 0),
                seconds=config.get("seconds", 0)
            )

        elif schedule_type == "cron":
            return CronTrigger(
                year=config.get("year"),
                month=config.get("month"),
                day=config.get("day"),
                week=config.get("week"),
                day_of_week=config.get("day_of_week"),
                hour=config.get("hour"),
                minute=config.get("minute"),
                second=config.get("second", 0)
            )

        return None

    async def _run_job(self, job_id: str):
        """Execute a scheduled job."""
        job = self._jobs.get(job_id)
        if not job:
            return

        self.job_started.emit(job_id)
        job.last_run = datetime.now()
        job.run_count += 1

        try:
            # Load project
            project = ScraperProject.load(job.project_path)

            # Run scraper
            orchestrator = ScraperOrchestrator(project)
            results = await orchestrator.run()
            await orchestrator.close()

            success_count = sum(1 for r in results if r.success)
            job.last_status = f"Success: {success_count}/{len(results)}"

            self.job_completed.emit(job_id, True, len(results))

        except Exception as e:
            job.last_status = f"Error: {str(e)}"
            self.job_error.emit(job_id, str(e))

        finally:
            self._save_jobs()

    def remove_job(self, job_id: str):
        """Remove a scheduled job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save_jobs()

            if self._scheduler.running:
                try:
                    self._scheduler.remove_job(job_id)
                except Exception:
                    pass

            self.job_removed.emit(job_id)

    def enable_job(self, job_id: str):
        """Enable a job."""
        if job_id in self._jobs:
            self._jobs[job_id].enabled = True
            self._save_jobs()

            if self._scheduler.running:
                self._add_job_to_scheduler(self._jobs[job_id])

    def disable_job(self, job_id: str):
        """Disable a job."""
        if job_id in self._jobs:
            self._jobs[job_id].enabled = False
            self._save_jobs()

            if self._scheduler.running:
                try:
                    self._scheduler.remove_job(job_id)
                except Exception:
                    pass

    def get_jobs(self) -> list[ScheduledJob]:
        """Get all scheduled jobs."""
        return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a specific job."""
        return self._jobs.get(job_id)

    def get_next_run_time(self, job_id: str) -> Optional[datetime]:
        """Get next run time for a job."""
        if self._scheduler.running:
            apjob = self._scheduler.get_job(job_id)
            if apjob:
                return apjob.next_run_time
        return None

    def run_job_now(self, job_id: str):
        """Run a job immediately."""
        if job_id in self._jobs:
            asyncio.create_task(self._run_job(job_id))
