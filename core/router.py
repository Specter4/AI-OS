"""
Router
"""

from tools.router_ai import classify


def route_message(message: str):
    return classify(message)