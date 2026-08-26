"""Natural-language intent detection for the AI-OS conversation boundary."""

from __future__ import annotations


# Explicit command prefixes remain deterministic and take priority over the
# broader natural-language goal classifier.
_COMMANDS = (
    ("remember ", "memory_store"),
    ("recall ", "memory_recall"),
    ("research ", "research"),
)

# These verbs describe a request to make a change, investigate something, or
# perform a multi-step operation. They are deliberately conservative: normal
# questions should remain conversation unless they contain a clear action cue.
_GOAL_VERBS = {
    "build", "create", "make", "design", "develop", "implement", "set up",
    "setup", "install", "configure", "find", "search", "compare", "analyze",
    "investigate", "organize", "plan", "prepare", "write", "generate",
    "download", "open", "visit", "check", "run", "execute", "automate",
    "schedule", "book", "buy", "purchase", "send", "deploy", "fix",
    "update", "research", "look for", "look up",
}

# Questions that contain an action verb but are asking for an explanation are
# still ordinary conversation.
_EXPLANATION_PREFIXES = (
    "what is ", "what are ", "what's ", "who is ", "why is ", "why are ",
    "how is ", "how does ", "how do ", "can you explain ", "tell me about ",
    "do you know ",
)


def _contains_goal_verb(text: str) -> bool:
    return any(
        text == verb or text.startswith(verb + " ") or f" {verb} " in text
        for verb in _GOAL_VERBS
    )


def detect_intent(message: str) -> dict[str, str]:
    """Classify a message into a small, deterministic AI-OS intent set.

    ``autonomous_goal`` is the bridge between natural conversation and the
    execution system. It intentionally does not call an LLM: routing must be
    reliable and must not fail merely because an LLM provider is unavailable.
    """
    text = message.lower().strip()

    for prefix, intent in _COMMANDS:
        if text.startswith(prefix):
            return {"intent": intent, "content": message[len(prefix):]}

    # Preserve explicit planner semantics used by the existing command flow.
    if _contains_goal_verb(text):
        if text.startswith(_EXPLANATION_PREFIXES):
            return {"intent": "conversation", "content": message}
        return {"intent": "autonomous_goal", "content": message}

    return {"intent": "conversation", "content": message}
