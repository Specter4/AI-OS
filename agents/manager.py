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


def _execute_goal(content: str):
    """Plan and execute a natural-language goal through the normal pipeline."""
    log("Autonomous Goal selected")
    tasks = plan(content)
    project = execute(tasks, goal=content)

    response = "## 🤖 AI-OS Execution Report\n\n"
    response += f"**Goal:** {project.goal}\n"
    response += f"**Status:** {project.status}\n"
    response += f"**Progress:** {project.progress()}%\n\n"

    for task in project.tasks:
        response += f"### {task.title}\n"
        response += f"- Agent: `{task.agent}`\n"
        response += f"- Status: `{task.status}`\n"
        if task.result is not None:
            preview = str(task.result)
            if len(preview) > 500:
                preview = preview[:500] + "..."
            response += f"- Result: {preview}\n"
        if task.error:
            response += f"- Error: {task.error}\n"
        response += "\n"

    return response


def handle_request(request):
    """Handle a structured conversation request."""
    intent = request["intent"]
    content = request["content"]

    log(f"Manager received intent: {intent}")

    if intent == "conversation":
        log("Conversation Engine selected")
        return respond(content)

    if intent in {"planner", "autonomous_goal"}:
        return _execute_goal(content)

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
