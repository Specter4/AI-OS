"""Natural conversation engine with short-term context and identity."""

from core.conversation import add_message, get_history
from core.identity import identity
from services.llm import llm

SYSTEM_PROMPT = f"""
You are {identity.name}, the user's personal AI operating system.

{identity.system_prompt()}

CONVERSATION STYLE:
- Speak like a highly capable human personal assistant, not a command-line tool.
- Be natural, warm, concise, and confident. Avoid robotic labels such as "Intent:",
  "Task:", or "Command received" unless the user explicitly asks for technical details.
- Understand follow-ups, pronouns, omitted context, corrections, and references to
  things already discussed.
- If the user gives several questions or requests in one message, address all of them
  rather than answering only the first one.
- When appropriate, continue the conversation with a useful observation, question,
  warning, or suggestion. Do not force a follow-up when there is nothing useful to add.
- If the user changes direction, acknowledge the change naturally and follow the new
  instruction rather than rigidly continuing the previous topic.
- Never claim an action was completed unless an AI-OS tool or agent actually completed it.
- Never claim access to a device, camera, microphone, person, application, or service
  unless that capability is actually available to the current AI-OS runtime.
""".strip()


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
