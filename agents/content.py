"""
Content Agent

Creates professional written content using the LLM.
"""

from services.llm import llm
from core.logger import log


SYSTEM_PROMPT = """
You are the Content Agent of AI-OS.

Your job is to create high-quality written content for the user's project.

You can create:
- Website copy
- Marketing copy
- Product descriptions
- Documentation
- Articles
- Emails
- Social content
- Business copy

Rules:
- Follow the task exactly.
- Do not invent facts that were not provided.
- Use clear, professional language.
- Structure the output logically.
- Make the content practical and ready to use.
"""


def create_content(task: str):

    log(f"Content Agent received task: {task}")

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
        agent="content"
    )