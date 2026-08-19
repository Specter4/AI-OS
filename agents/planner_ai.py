"""
AI Planner

Uses an AI model to create an execution plan.
"""

from services.llm import llm
from core.logger import log


def create_plan(goal: str):

    log(f"AI Planner received goal: {goal}")

    prompt = f"""
You are the planning engine of an autonomous AI operating system.

Your job is to break the user's goal into small, executable tasks.

AI-OS can execute independent tasks in parallel.

Therefore, identify which tasks depend on earlier tasks.

Return ONLY a numbered list.

Every task MUST use this format:

1. Task description | agent | depends: none
2. Task description | agent | depends: 1
3. Task description | agent | depends: 1,2

Valid agents:

assistant
research
browser
planner
content
design
coding
review

Rules:

- Use "depends: none" when a task has no dependencies.
- Use task numbers for dependencies.
- A task should depend on another task only when it genuinely needs that task's result.
- Independent research tasks should normally run in parallel.
- Content and design can run in parallel when they use the same research.
- Coding should depend on the relevant content/design tasks.
- Review should depend on the work it needs to review.
- Deployment should depend on successful testing.
- Do not create unnecessary dependencies.
- Keep tasks concrete and executable.
- Do not explain your reasoning.
- Return ONLY the numbered task list.

Example:

1. Research dental industry trends | research | depends: none
2. Research competitor websites | browser | depends: none
3. Identify target audience | research | depends: none
4. Create website strategy | planner | depends: 1,3
5. Write website copy | content | depends: 4
6. Design website interface | design | depends: 4
7. Build frontend | coding | depends: 5,6
8. Test website | review | depends: 7
9. Fix issues found during testing | coding | depends: 8
10. Deploy website | browser | depends: 9

Goal:

{goal}
"""

    messages = [
        {
            "role": "system",
            "content": "You are the autonomous planning engine of AI-OS."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    result = llm.generate(
        messages,
        agent="planner"
    )

    if result.success:

        return result.output

    raise RuntimeError(result.error)