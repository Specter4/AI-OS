"""
Task Executor

Dependency-aware autonomous task execution engine.

Features:
- Normalizes incoming tasks
- Creates Project state
- Uses Supervisor for execution control
- Respects task dependencies
- Runs independent tasks in parallel
- Stores results in shared project context
- Handles failures and retries
- Prevents dependent tasks from running after failed prerequisites
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from core.logger import log
from core.project import Project
from core.tasks import Task
from workflow.dispatcher import dispatch
from agents.supervisor import Supervisor


# ==========================================================
# TASK NORMALIZATION
# ==========================================================

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
            depends_on=task.get("depends_on", [])
        )

    if isinstance(task, str):

        return Task(
            id=task_id,
            title=task,
            agent="assistant"
        )

    raise TypeError(
        f"Unsupported task type: {type(task).__name__}"
    )


# ==========================================================
# DEPENDENCY CHECK
# ==========================================================

def dependencies_satisfied(task, task_map):

    for dependency_id in task.depends_on:

        dependency = task_map.get(dependency_id)

        if dependency is None:

            return False

        if dependency.status != "completed":

            return False

    return True


# ==========================================================
# DEPENDENCY FAILURE CHECK
# ==========================================================

def dependency_failed(task, task_map):

    for dependency_id in task.depends_on:

        dependency = task_map.get(dependency_id)

        if dependency is None:

            continue

        if dependency.status == "failed":

            return True

    return False


# ==========================================================
# EXECUTE SINGLE TASK
# ==========================================================

def execute_task(task, supervisor, project):

    supervisor.task_started(task)

    try:

        log(
            f"Dispatching Task {task.id} "
            f"to {task.agent}"
        )

        result = dispatch(task)

        task.result = result

        project.save(
            f"task_{task.id}",
            result
        )

        supervisor.task_completed(task)

        return task

    except Exception as e:

        error = str(e)

        log(
            f"Task {task.id} failed: {error}"
        )

        decision = supervisor.task_failed(
            task,
            error
        )

        if decision == "retry":

            task.status = "pending"

        return task


# ==========================================================
# MAIN EXECUTOR
# ==========================================================

def execute(goal, tasks):

    log("Starting task execution...")

    # ------------------------------------------------------
    # Normalize tasks
    # ------------------------------------------------------

    normalized_tasks = []

    for index, task in enumerate(tasks, start=1):

        normalized_task = normalize_task(
            task,
            index
        )

        normalized_tasks.append(
            normalized_task
        )

    # ------------------------------------------------------
    # Create project
    # ------------------------------------------------------

    project = Project(
        goal=goal,
        tasks=normalized_tasks
    )

    # ------------------------------------------------------
    # Task lookup
    # ------------------------------------------------------

    task_map = {
        task.id: task
        for task in project.tasks
    }

    # ------------------------------------------------------
    # Supervisor
    # ------------------------------------------------------

    supervisor = Supervisor(project)

    supervisor.start()

    log(
        f"Dependency graph contains "
        f"{len(project.tasks)} tasks."
    )

    # ------------------------------------------------------
    # Parallel execution pool
    # ------------------------------------------------------

    max_workers = min(
        8,
        max(1, len(project.tasks))
    )

    executor = ThreadPoolExecutor(
        max_workers=max_workers
    )

    try:

        # ==================================================
        # EXECUTION LOOP
        # ==================================================

        while True:

            # ------------------------------------------------
            # Check completion
            # ------------------------------------------------

            unfinished = [
                task
                for task in project.tasks
                if task.status not in {
                    "completed",
                    "failed",
                    "blocked"
                }
            ]

            if not unfinished:
                break

            # ------------------------------------------------
            # Block tasks whose dependencies failed
            # ------------------------------------------------

            for task in unfinished:

                if dependency_failed(
                    task,
                    task_map
                ):

                    task.status = "blocked"

                    task.result = (
                        "Blocked because one or more "
                        "dependencies failed."
                    )

                    log(
                        f"Task {task.id} blocked: "
                        f"dependency failure."
                    )

            # ------------------------------------------------
            # Find ready tasks
            # ------------------------------------------------

            ready_tasks = []

            for task in project.tasks:

                if task.status != "pending":
                    continue

                if dependency_failed(
                    task,
                    task_map
                ):
                    continue

                if dependencies_satisfied(
                    task,
                    task_map
                ):

                    ready_tasks.append(task)

            # ------------------------------------------------
            # Nothing ready
            # ------------------------------------------------

            if not ready_tasks:

                remaining = [
                    task
                    for task in project.tasks
                    if task.status not in {
                        "completed",
                        "failed",
                        "blocked"
                    }
                ]

                if remaining:

                    log(
                        "No executable tasks remain. "
                        "Possible circular or invalid "
                        "dependency graph."
                    )

                    for task in remaining:

                        task.status = "blocked"

                        task.result = (
                            "Blocked because its "
                            "dependencies could not "
                            "be satisfied."
                        )

                break

            # ------------------------------------------------
            # Prioritize tasks
            # ------------------------------------------------

            ready_tasks.sort(
                key=lambda task: (
                    -task.priority,
                    task.id
                )
            )

            log(
                f"Starting parallel batch: "
                f"{len(ready_tasks)} tasks"
            )

            # ------------------------------------------------
            # Submit ready tasks concurrently
            # ------------------------------------------------

            futures = {}

            for task in ready_tasks:

                future = executor.submit(
                    execute_task,
                    task,
                    supervisor,
                    project
                )

                futures[future] = task

            # ------------------------------------------------
            # Wait for batch
            # ------------------------------------------------

            for future in as_completed(futures):

                task = futures[future]

                try:

                    future.result()

                except Exception as e:

                    log(
                        f"Unexpected executor error "
                        f"for Task {task.id}: {e}"
                    )

                    task.status = "failed"

                    task.result = str(e)

            log("Parallel batch completed.")

    finally:

        executor.shutdown(
            wait=True
        )

    # ========================================================
    # FINISH
    # ========================================================

    supervisor.finish()

    log(
        f"Project finished "
        f"({project.progress()}%)"
    )

    return project