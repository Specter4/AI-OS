"""
AI-OS Manager Agent

Receives structured requests from the Conversation Engine
and delegates them to the appropriate agent.
"""

from agents.memory import remember, recall
from agents.research import research
from agents.planner import plan
from conversation.engine import respond

from workflow.executor import execute
from core.logger import log


def handle_request(request):
    """Handle a structured conversation request."""
    intent = request["intent"]
    content = request["content"]

    log(f"Manager received intent: {intent}")

    if intent == "conversation":
        log("Conversation Engine selected")
        return respond(content)

    if intent == "planner":
        log("Planner Agent selected")
        tasks = plan(content)
        project = execute(tasks, goal=content)
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

    if intent == "memory_store":
        try:
            key, value = content.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            remember(key, value)
            log(f"Memory stored: {key}")
            return f"✅ I will remember **{key}** = **{value}**"
        except ValueError:
            return "❌ Usage:\nremember company = AI-OS"

    if intent == "memory_recall":
        key = content.strip().lower()
        value = recall(key)
        log(f"Memory lookup: {key}")
        if value:
            return f"🧠 **{key}** = **{value}**"
        return f"❌ I don't remember anything about **{key}**."

    if intent == "research":
        log("Research Agent selected")
        return research(content)

    log(f"Unknown intent: {intent}")
    return "❌ Sorry, I don't know how to handle that request yet."
