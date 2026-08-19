"""
Ollama Client

Provides a single interface for all local LLM calls.
"""

import ollama
from core.config import DEFAULT_MODEL


def chat(prompt, system_prompt=None, model=None):
    """
    Send a prompt to an Ollama model.
    """

    if model is None:
        model = DEFAULT_MODEL

    messages = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    messages.append({
        "role": "user",
        "content": prompt
    })

    response = ollama.chat(
        model=model,
        messages=messages
    )

    return response["message"]["content"]