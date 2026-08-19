"""
Research Agent
"""

from services.llm import llm


SYSTEM_PROMPT = """
You are a professional research analyst.

Your job is to produce concise, well-structured reports.

Always respond using this format:

# Objective

# Key Findings

# Opportunities

# Risks

# Recommended Next Steps
"""


def research(topic: str):

    messages = [

        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },

        {
            "role": "user",
            "content": topic
        }

    ]

    return llm.generate(
    messages,
    agent="research"
)