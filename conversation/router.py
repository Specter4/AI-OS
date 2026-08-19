"""
Conversation Router

Routes all user messages into structured requests.
"""

from conversation.intent import detect_intent


def route(message: str):
    """
    Converts a user message into a request
    understood by the Manager.
    """

    request = detect_intent(message)

    return request