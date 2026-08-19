"""
Conversation Manager

Stores the recent conversation history for AI-OS.
"""

MAX_HISTORY = 20

_history = []


def add_message(role: str, content: str):
    """
    Add a message to the conversation history.

    role:
        "user"
        "assistant"
        "system"
    """

    global _history

    _history.append({
        "role": role,
        "content": content
    })

    # Keep only the newest messages
    if len(_history) > MAX_HISTORY:
        _history = _history[-MAX_HISTORY:]


def get_history():
    """
    Return a copy of the current conversation.
    """

    return list(_history)


def clear():
    """
    Clear the conversation history.
    """

    global _history
    _history = []