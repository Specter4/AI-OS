import pytest

from workflow.planner import GoalPlanner


def test_empty_goal_is_rejected():
    with pytest.raises(ValueError):
        GoalPlanner().plan("   ")


def test_single_natural_request_remains_one_task():
    plan = GoalPlanner().plan("Check the weather for tomorrow.")
    assert len(plan.tasks) == 1
    assert plan.tasks[0].description == "Check the weather for tomorrow"
    assert not plan.is_multi_task


def test_multiple_requests_become_ordered_tasks():
    plan = GoalPlanner().plan(
        "Research the best laptop, compare the options, and recommend one."
    )
    assert plan.is_multi_task
    assert [task.task_id for task in plan.tasks] == [1, 2, 3]
    assert plan.tasks[1].depends_on == (1,)
    assert plan.tasks[2].depends_on == (2,)
    assert "Research" in plan.tasks[0].description
    assert "compare" in plan.tasks[1].description
    assert "recommend" in plan.tasks[2].description


def test_then_and_also_are_natural_task_boundaries():
    plan = GoalPlanner().plan("Find my files, then summarize them, also draft an email.")
    assert len(plan.tasks) == 3
    assert [task.depends_on for task in plan.tasks] == [(), (1,), (2,)]
