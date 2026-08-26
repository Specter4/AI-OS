"""Natural conversation engine with short-term context."""

from core.conversation import add_message, get_history
from services.llm import llm

SYSTEM_PROMPT = """
You are AI-OS, the user's personal AI operating system.

Use recent conversation history to understand follow-ups, pronouns, and omitted context.
Be accurate and concise unless the user asks for detail.
Do not claim an action was completed unless an AI-OS tool or agent actually completed it.
"""


def respond(message: str):
    """Generate a context-aware response and persist the exchange."""
    add_message("user", message)
    result = llm.generate(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            *get_history(),
        ],
        agent="conversation",
    )
    if result.success:
        add_message("assistant", result.output)
    return result
