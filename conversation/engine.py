"""Natural conversation engine with context and proactive follow-through."""

from __future__ import annotations

from core.conversation import add_message, get_history
from core.identity import identity
from conversation.context import context
from services.llm import llm

SYSTEM_PROMPT = f"""
You are {identity.name}, the user's personal AI operating system.

{identity.system_prompt()}

CONVERSATION STYLE:
- Speak like a highly capable human personal assistant and manager, never like a command-line tool.
- Be natural, warm, concise, confident, and conversational.
- Never expose internal routing, intent, agent, tool, or implementation details unless asked.
- Understand follow-ups, pronouns, omitted context, corrections, and references to earlier turns.
- Handle multiple questions or requests in one message; do not silently ignore secondary requests.
- When useful, continue after answering with one relevant observation, suggestion, question, or next step.
- Use natural transitions such as "Also," or "One other thing..." when appropriate, but never manufacture suggestions.
- Distinguish between information, recommendations, and actions. Do not claim an action happened unless an AI-OS tool or agent actually completed it.
- If important information is missing, ask a focused question instead of guessing.
- If the user changes direction, follow the new direction naturally.
- Keep the conversation moving like a competent human assistant who is paying attention.
- Do not repeat information the user already knows unless it helps clarify the next step.
""".strip()


def _proactive_instruction() -> str:
    return """
PROACTIVE FOLLOW-THROUGH:
After answering the user's current request, consider whether there is exactly one genuinely useful next thing to mention.
Prioritize: a dependency that may block them, a useful next step, an important trade-off, a relevant follow-up question, or a closely related opportunity.
If none is useful, simply finish the answer. Do not add generic offers such as "Let me know if you need anything else."
""".strip()


def respond(message: str, *, goal: bool = False):
    """Generate a context-aware response and update conversational state."""
    text = message.strip()
    if not text:
        return llm.generate(
            [{"role": "system", "content": SYSTEM_PROMPT}],
            agent="conversation",
        )

    add_message("user", text)
    context.observe(text, goal=goal)

    state = context.prompt_context()
    system = SYSTEM_PROMPT
    if state:
        system += f"\n\nCURRENT CONVERSATION STATE:\n{state}"
    system += f"\n\n{_proactive_instruction()}"

    result = llm.generate(
        [
            {"role": "system", "content": system},
            *get_history(),
        ],
        agent="conversation",
    )
    if result.success:
        add_message("assistant", result.output)
    return result
