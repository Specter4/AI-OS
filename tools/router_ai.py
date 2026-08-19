"""
AI Router

Uses the local LLM to classify requests.
"""

import json

from tools.ollama_client import chat

SYSTEM_PROMPT = """
You are the routing engine for AI-OS.

Analyze the user's message.

Return ONLY valid JSON.

Example:

{
  "intent": "conversation",
  "agent": "assistant",
  "content": "original user message"
}

Allowed intents:

conversation
memory_store
memory_recall
research
coding

Allowed agents:

assistant
memory
research

Do not explain anything.

Return JSON only.
"""


def classify(message: str):

    response = chat(
        prompt=message,
        system_prompt=SYSTEM_PROMPT
    )

    try:
        return json.loads(response)

    except Exception:

        return {
            "intent": "conversation",
            "agent": "assistant",
            "content": message
        }