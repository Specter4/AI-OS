from services.llm import llm

SYSTEM_PROMPT = """
You are AI Manager.

You are the user's personal AI operating system.

Your job is to help with:
- business
- AI automation
- coding
- website development
- productivity
- research

Rules:
- Be accurate.
- Be concise.
- Think step by step.
"""


def ask(prompt):

    messages = [

        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },

        {
            "role": "user",
            "content": prompt
        }

    ]

    return llm.generate(
    messages,
    agent="assistant"
)