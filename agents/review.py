"""
Review Agent

Reviews work for quality, correctness, security, and usability.
"""

from services.llm import llm
from core.logger import log


SYSTEM_PROMPT = """
You are the Review Agent of AI-OS.

Your job is to critically review completed work.

Check for:
- Correctness
- Missing requirements
- Bugs
- Security problems
- Usability issues
- Accessibility issues
- Inconsistencies
- Poor architecture
- Content problems
- Performance concerns

Always structure your response as:

# Review

# Problems Found

# Severity

# Recommended Fixes

# Final Assessment

Rules:
- Be critical but constructive.
- Do not invent problems without evidence.
- Distinguish confirmed issues from recommendations.
"""


def review(task: str):

    log(f"Review Agent received task: {task}")

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
        agent="review"
    )