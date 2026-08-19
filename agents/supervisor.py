"""
Supervisor Agent

Monitors project execution and makes decisions.
"""

from core.logger import log


class Supervisor:

    MAX_RETRIES = 2

    def __init__(self, project):

        self.project = project

        self.retry_counts = {}

    # ----------------------------------

    def start(self):

        self.project.status = "running"

        log(f"Supervisor started: {self.project.goal}")

    # ----------------------------------

    def task_started(self, task):

        task.status = "running"

        log(f"Running Task {task.id}: {task.title}")

    # ----------------------------------

    def task_completed(self, task):

        task.status = "completed"

        log(f"Completed Task {task.id}")

    # ----------------------------------

    def task_failed(self, task, reason):

        task.status = "failed"

        self.project.notes.append(
            f"{task.title}: {reason}"
        )

        retries = self.retry_counts.get(task.id, 0)

        if retries < self.MAX_RETRIES:

            self.retry_counts[task.id] = retries + 1

            log(
                f"Retrying Task {task.id} "
                f"({retries+1}/{self.MAX_RETRIES})"
            )

            return "retry"

        log(
            f"Task {task.id} permanently failed."
        )

        return "skip"

    # ----------------------------------

    def finish(self):

        if self.project.failed_tasks():

            self.project.status = "completed_with_errors"

        else:

            self.project.status = "completed"

        log(
            f"Project finished "
            f"({self.project.progress()}%)"
        )