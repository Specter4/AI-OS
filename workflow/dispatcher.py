"""
Task Dispatcher

Routes tasks to the correct agent and gives agents
access to the shared project context.
"""

from core.logger import log

from agents.assistant import ask
from agents.research import research
from agents.browser import browser_agent
from agents.content import create_content
from agents.design import design
from agents.coding import code
from agents.review import review


def build_prompt(task, project):
    """
    Build an agent prompt containing:
    - The current task
    - Relevant previous task results
    """

    prompt = f"""
CURRENT TASK

Task ID: {task.id}
Task: {task.title}
Agent: {task.agent}
"""

    if not task.depends_on:
        return prompt

    prompt += """

UPSTREAM TASK RESULTS

The following tasks were completed before this task.
Use their results as context. Do not ignore them.
"""

    for dependency_id in task.depends_on:

        result = project.load(
            f"task_{dependency_id}"
        )

        if result is None:
            continue

        prompt += f"""

--- Task {dependency_id} Result ---

{result}

--- End Task {dependency_id} ---
"""

    return prompt


def dispatch(task, project=None):

    log(
        f"Dispatching Task {task.id} "
        f"to {task.agent}"
    )

    if project is not None:
        prompt = build_prompt(task, project)
    else:
        prompt = task.title

    if task.agent == "assistant":
        return ask(prompt)

    elif task.agent == "research":
        return research(prompt)

    elif task.agent == "browser":
        return browser_agent.execute(task.title)

    elif task.agent == "planner":
        return "Planner task completed."

    elif task.agent == "content":
        return create_content(prompt)

    elif task.agent == "design":
        return design(prompt)

    elif task.agent == "coding":
        return code(prompt)

    elif task.agent == "review":
        return review(prompt)

    log(f"Unknown agent: {task.agent}")

    return {
        "success": False,
        "error": f"Unknown agent: {task.agent}"
    }
