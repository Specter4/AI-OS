"""
Task Executor

Dependency-aware autonomous task execution engine.

Features:
- Normalizes and validates incoming tasks
- Detects invalid and circular dependency graphs before execution
- Uses Supervisor for execution control and retries
- Runs independent tasks in parallel
- Passes shared project context into agents
- Treats unsuccessful AgentResult values as task failures
- Blocks tasks whose prerequisites cannot complete
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os

from core.logger import log
from core.project import Project
from core.result import AgentResult
from core.tasks import Task
from workflow.dispatcher import dispatch
from agents.supervisor import Supervisor


TERMINAL_STATES = {"completed", "failed", "blocked"}


def normalize_task(task, task_id):
    if isinstance(task, Task):
        return task

    if isinstance(task, dict):
        return Task(
            id=task.get("id", task_id),
            title=task.get("title", "Unnamed task"),
            agent=task.get("agent", "assistant"),
            priority=task.get("priority", 1),
            status=task.get("status", "pending"),
            metadata=task.get("metadata", {}),
            depends_on=task.get("depends_on", []),
        )

    if isinstance(task, str):
        return Task(
            id=task_id,
            title=task,
            agent="assistant",
        )

    raise TypeError(
        f"Unsupported task type: {type(task).__name__}"
    )


def validate_dependency_graph(tasks):
    """Validate IDs and detect missing dependencies/cycles."""
    task_map = {task.id: task for task in tasks}

    if len(task_map) != len(tasks):
        raise ValueError("Task IDs must be unique.")

    for task in tasks:
        if task.id in task.depends_on:
            raise ValueError(
                f"Task {task.id} cannot depend on itself."
            )

        missing = [
            dep_id
            for dep_id in task.depends_on
            if dep_id not in task_map
        ]
        if missing:
            raise ValueError(
                f"Task {task.id} has missing dependencies: {missing}"
            )

    # DFS cycle detection.
    visiting = set()
    visited = set()

    def visit(task_id):
        if task_id in visiting:
            raise ValueError("Circular task dependency detected.")
        if task_id in visited:
            return

        visiting.add(task_id)
        for dependency_id in task_map[task_id].depends_on:
            visit(dependency_id)
        visiting.remove(task_id)
        visited.add(task_id)

    for task in tasks:
        visit(task.id)

    return task_map


def dependencies_satisfied(task, task_map):
    return all(
        task_map[dependency_id].status == "completed"
        for dependency_id in task.depends_on
    )


def dependency_blocked(task, task_map):
    return any(
        task_map[dependency_id].status in {"failed", "blocked"}
        for dependency_id in task.depends_on
    )


def result_is_successful(result):
    """Interpret standardized AgentResult values correctly."""
    if isinstance(result, AgentResult):
        return result.success

    # Preserve compatibility with agents that return plain values.
    if isinstance(result, dict) and "success" in result:
        return bool(result["success"])

    return True


def execute_task(task, supervisor, project):
    supervisor.task_started(task)

    try:
        log(
            f"Dispatching Task {task.id} "
            f"to {task.agent}"
        )

        result = dispatch(task, project=project)

        if not result_is_successful(result):
            if isinstance(result, AgentResult):
                error = result.error or "Agent reported failure."
            elif isinstance(result, dict):
                error = result.get("error", "Agent reported failure.")
            else:
                error = "Agent reported failure."
            raise RuntimeError(error)

        task.result = result
        project.save(f"task_{task.id}", result)
        supervisor.task_completed(task)
        return task

    except Exception as exc:
        error = str(exc)
        log(f"Task {task.id} failed: {error}")

        supervisor.task_failed(task, error)
        return task


def execute(goal, tasks):
    log("Starting task execution...")

    normalized_tasks = [
        normalize_task(task, index)
        for index, task in enumerate(tasks, start=1)
    ]

    project = Project(
        goal=goal,
        tasks=normalized_tasks,
    )

    task_map = validate_dependency_graph(project.tasks)

    supervisor = Supervisor(project)
    supervisor.start()

    log(
        f"Dependency graph contains "
        f"{len(project.tasks)} tasks."
    )

    requested_workers = int(
        os.getenv("AIOS_MAX_WORKERS", "8")
    )
    max_workers = min(
        max(1, requested_workers),
        max(1, len(project.tasks)),
    )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        while True:
            unfinished = [
                task
                for task in project.tasks
                if task.status not in TERMINAL_STATES
            ]

            if not unfinished:
                break

            # Propagate permanent dependency failures.
            for task in unfinished:
                if dependency_blocked(task, task_map):
                    task.status = "blocked"
                    task.result = (
                        "Blocked because a required dependency "
                        "failed or was blocked."
                    )
                    log(
                        f"Task {task.id} blocked: "
                        "dependency failure."
                    )

            ready_tasks = [
                task
                for task in project.tasks
                if task.status == "pending"
                and not dependency_blocked(task, task_map)
                and dependencies_satisfied(task, task_map)
            ]

            if not ready_tasks:
                remaining = [
                    task
                    for task in project.tasks
                    if task.status not in TERMINAL_STATES
                ]

                if remaining:
                    for task in remaining:
                        task.status = "blocked"
                        task.result = (
                            "Blocked because its dependencies "
                            "could not be satisfied."
                        )
                    log(
                        "No executable tasks remain; remaining tasks "
                        "were blocked."
                    )
                break

            ready_tasks.sort(
                key=lambda task: (-task.priority, task.id)
            )

            log(
                f"Starting parallel batch: "
                f"{len(ready_tasks)} tasks"
            )

            futures = {
                pool.submit(
                    execute_task,
                    task,
                    supervisor,
                    project,
                ): task
                for task in ready_tasks
            }

            for future in as_completed(futures):
                task = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    # execute_task normally catches agent failures, but keep
                    # the executor resilient to unexpected worker failures.
                    log(
                        f"Unexpected executor error for "
                        f"Task {task.id}: {exc}"
                    )
                    task.status = "failed"
                    task.result = str(exc)

            log("Parallel batch completed.")

    supervisor.finish()

    log(
        f"Project finished "
        f"({project.progress()}%)"
    )

    return project
