from core.tasks import Task
from workflow.orchestrator import TaskOrchestrator


def test_build_converts_natural_goal_into_executable_tasks():
    tasks = TaskOrchestrator().build(
        "Research the best laptop, compare the options, and recommend one."
    )

    assert len(tasks) == 3
    assert all(isinstance(task, Task) for task in tasks)
    assert [task.id for task in tasks] == [1, 2, 3]
    assert tasks[0].depends_on == []
    assert tasks[1].depends_on == [1]
    assert tasks[2].depends_on == [2]


def test_orchestrator_assigns_reasonable_agents():
    tasks = TaskOrchestrator().build("Research laptops and draft a recommendation.")

    assert tasks[0].agent == "research"
    assert tasks[1].agent == "content"


def test_plan_metadata_is_preserved():
    tasks = TaskOrchestrator().build("Check the project status.")

    assert tasks[0].metadata["planned"] is True
    assert tasks[0].metadata["goal"] == "Check the project status"
