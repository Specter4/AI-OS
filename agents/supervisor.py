"""
Supervisor Agent

Monitors project execution and makes decisions.
"""

from threading import RLock

from core.logger import log


class Supervisor:

    MAX_RETRIES = 2

    def __init__(self, project):
        self.project = project
        self.retry_counts = {}
        self._lock = RLock()

    def start(self):
        with self._lock:
            self.project.status = "running"
        log(f"Supervisor started: {self.project.goal}")

    def task_started(self, task):
        with self._lock:
            task.status = "running"
        log(f"Running Task {task.id}: {task.title}")

    def task_completed(self, task):
        with self._lock:
            task.status = "completed"
        log(f"Completed Task {task.id}")

    def task_failed(self, task, reason):
        with self._lock:
            retries = self.retry_counts.get(task.id, 0)
            self.project.notes.append(
                f"{task.title}: {reason}"
            )

            if retries < self.MAX_RETRIES:
                self.retry_counts[task.id] = retries + 1
                task.status = "pending"
                retry_number = retries + 1
                should_retry = True
            else:
                task.status = "failed"
                retry_number = retries
                should_retry = False

        if should_retry:
            log(
                f"Retrying Task {task.id} "
                f"({retry_number}/{self.MAX_RETRIES})"
            )
            return "retry"

        log(f"Task {task.id} permanently failed.")
        return "skip"

    def finish(self):
        with self._lock:
            if self.project.failed_tasks() or any(
                task.status == "blocked" for task in self.project.tasks
            ):
                self.project.status = "completed_with_errors"
            else:
                self.project.status = "completed"

        log(
            f"Project finished "
            f"({self.project.progress()}%)"
        )
