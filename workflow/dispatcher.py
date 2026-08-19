"""
Task Dispatcher

Routes tasks to the correct agent and gives agents
access to the shared project context.
"""

from core.logger import log

from agents.assistant import ask
from agents.research import research
from agents.browser import browser_agent
from agents.content import write_content
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

    # --------------------------------------------------
    # Build context-aware prompt
    # --------------------------------------------------

    if project is not None:

        prompt = build_prompt(
            task,
            project
        )

    else:

        prompt = task.title

    # --------------------------------------------------
    # Assistant
    # --------------------------------------------------

    if task.agent == "assistant":

        return ask(prompt)

    # --------------------------------------------------
    # Research
    # --------------------------------------------------

    elif task.agent == "research":

        return research(prompt)

    # --------------------------------------------------
    # Browser
    # --------------------------------------------------

    elif task.agent == "browser":

        return browser_agent.execute(
            task.title
        )

    # --------------------------------------------------
    # Planner
    # --------------------------------------------------

    elif task.agent == "planner":

        return "Planner task completed."

    # --------------------------------------------------
    # Content
    # --------------------------------------------------

    elif task.agent == "content":

        return write_content(prompt)

    # --------------------------------------------------
    # Design
    # --------------------------------------------------

    elif task.agent == "design":

        return design(prompt)

    # --------------------------------------------------
    # Coding
    # --------------------------------------------------

    elif task.agent == "coding":

        return code(prompt)

    # --------------------------------------------------
    # Review
    # --------------------------------------------------

    elif task.agent == "review":

        return review(prompt)

    # --------------------------------------------------
    # Unknown agent
    # --------------------------------------------------

    log(
        f"Unknown agent: {task.agent}"
    )

    return {
        "success": False,
        "error": (
            f"Unknown agent: {task.agent}"
        )
    }