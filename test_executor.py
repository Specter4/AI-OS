import unittest
from unittest.mock import patch

from core.result import AgentResult
from core.tasks import Task
from workflow.executor import execute


class ExecutorTests(unittest.TestCase):

    def test_dependencies_run_in_stages(self):
        calls = []

        def fake_dispatch(task, project=None):
            calls.append(task.id)
            return AgentResult(
                success=True,
                agent=task.agent,
                output=f"done {task.id}",
            )

        tasks = [
            Task(1, "Research", "research"),
            Task(2, "Write", "content", depends_on=[1]),
            Task(3, "Build", "coding", depends_on=[2]),
        ]

        with patch("workflow.executor.dispatch", side_effect=fake_dispatch):
            project = execute("dependency test", tasks)

        self.assertEqual(project.status, "completed")
        self.assertEqual(project.progress(), 100)
        self.assertEqual(calls, [1, 2, 3])

    def test_agent_failure_blocks_dependents(self):
        def fake_dispatch(task, project=None):
            return AgentResult(
                success=False,
                agent=task.agent,
                output="",
                error="simulated failure",
            )

        tasks = [
            Task(1, "Fail", "assistant"),
            Task(2, "Dependent", "coding", depends_on=[1]),
        ]

        with patch("workflow.executor.dispatch", side_effect=fake_dispatch):
            project = execute("failure test", tasks)

        self.assertEqual(project.tasks[0].status, "failed")
        self.assertEqual(project.tasks[1].status, "blocked")
        self.assertEqual(project.status, "completed_with_errors")

    def test_circular_dependencies_are_rejected(self):
        tasks = [
            Task(1, "A", "assistant", depends_on=[2]),
            Task(2, "B", "assistant", depends_on=[1]),
        ]

        with self.assertRaises(ValueError):
            execute("cycle test", tasks)


if __name__ == "__main__":
    unittest.main()
