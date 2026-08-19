"""
Design Agent

Creates UI/UX and visual design specifications using the LLM.
"""

from services.llm import llm
from core.logger import log


SYSTEM_PROMPT = """
You are the Design Agent of AI-OS.

Your job is to design professional user interfaces and experiences.

You can create:
- Website layouts
- UI specifications
- UX flows
- Wireframes
- Design systems
- Color palettes
- Typography systems
- Component specifications
- Responsive layouts

Rules:
- Think like a professional UI/UX designer.
- Prioritize usability and accessibility.
- Explain layouts clearly enough for a coding agent to implement.
- Keep the design consistent.
- Consider desktop and mobile experiences.
"""


def design(task: str):

    log(f"Design Agent received task: {task}")

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": task
        }
    ]

    return llm.generate(
        messages,
        agent="design"
    )