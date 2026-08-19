"""
AI-OS Manager Agent

Receives structured requests from the Conversation Engine
and delegates them to the appropriate agent.
"""

from agents.assistant import ask
from agents.memory import remember, recall
from agents.research import research
from agents.planner import plan

from workflow.executor import execute

from core.logger import log


def handle_request(request):
    """
    Expected request format:

    {
        "intent": "...",
        "content": "..."
    }
    """

    intent = request["intent"]
    content = request["content"]

    log(f"Manager received intent: {intent}")

    # ==================================================
    # Conversation
    # ==================================================
    if intent == "conversation":

        log("Assistant Agent selected")

        return ask(content)

    # ==================================================
    # Planner
    # ==================================================
    elif intent == "planner":

        log("Planner Agent selected")

        # Create the project plan
        tasks = plan(content)

        # Execute the project
        project = execute(
            tasks,
            goal=content
        )
        response = "## 📋 Execution Report\n\n"

        for task in project.tasks:

            response += (
                f"📁 Project: {project.goal}\n"
                f"Status: {project.status}\n"
                f"Progress: {project.progress()}%\n\n"
            )
            if task.result:

                preview = str(task.result)

                if len(preview) > 100:
                    preview = preview[:100] + "..."

                response += f"- Result: {preview}\n"

            response += "\n"

        return response

    # ==================================================
    # Memory Store
    # ==================================================
    elif intent == "memory_store":

        try:

            key, value = content.split("=", 1)

            key = key.strip().lower()
            value = value.strip()

            remember(key, value)

            log(f"Memory stored: {key}")

            return f"✅ I will remember **{key}** = **{value}**"

        except ValueError:

            return (
                "❌ Usage:\n"
                "remember company = AI-OS"
            )

    # ==================================================
    # Memory Recall
    # ==================================================
    elif intent == "memory_recall":

        key = content.strip().lower()

        value = recall(key)

        log(f"Memory lookup: {key}")

        if value:
            return f"🧠 **{key}** = **{value}**"

        return f"❌ I don't remember anything about **{key}**."

    # ==================================================
    # Research
    # ==================================================
    elif intent == "research":

        log("Research Agent selected")

        return research(content)

    # ==================================================
    # Unknown
    # ==================================================
    else:

        log(f"Unknown intent: {intent}")

        return "❌ Sorry, I don't know how to handle that request yet."