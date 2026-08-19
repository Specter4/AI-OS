"""
Intent Detection

Converts natural language into AI-OS intents.
"""


def detect_intent(message: str):

    text = message.lower().strip()

    # -------------------------
    # Memory Store
    # -------------------------

    if text.startswith("remember "):

        return {
            "intent": "memory_store",
            "content": message[len("remember "):]
        }

    # -------------------------
    # Memory Recall
    # -------------------------

    if text.startswith("recall "):

        return {
            "intent": "memory_recall",
            "content": message[len("recall "):]
        }

    # -------------------------
    # Research
    # -------------------------

    if text.startswith("research "):

        return {
            "intent": "research",
            "content": message[len("research "):]
        }

    # -------------------------
    # Planner
    # -------------------------

    if (
        "build" in text
        or "create" in text
        or "make" in text
        or "design" in text
    ):

        return {
            "intent": "planner",
            "content": message
        }

    # -------------------------
    # Default Conversation
    # -------------------------

    return {
        "intent": "conversation",
        "content": message
    }