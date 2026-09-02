"""
AI-OS Manager Agent

Receives structured requests from the Conversation Engine
and delegates them to the appropriate agent.
"""

import hashlib

from agents.memory import remember, recall
from agents.research import research
from conversation.engine import respond
from core.logger import log
from workflow.mission import mission


def _mission_id(goal: str) -> str:
    """Create a stable local identifier for a natural-language mission."""
    digest = hashlib.sha256(goal.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"mission-{digest}"


def _execute_goal(content: str):
    """Run a natural-language objective through the durable mission pipeline."""
    log("Autonomous Goal selected")
    mission_id = _mission_id(content)
    project = mission.start(mission_id, content)
    report = mission.report(mission_id)

    response = "## 🤖 AI-OS Execution Report\n\n"
    response += f"**Mission:** `{mission_id}`\n"
    response += f"**Goal:** {report.goal}\n"
    response += f"**Status:** {report.status}\n"
    response += f"**Progress:** {report.progress}%\n\n"

    for task in report.tasks:
        response += f"### {task['title']}\n"
        response += f"- Agent: `{task['agent']}`\n"
        response += f"- Status: `{task['status']}`\n"
        if task["result"] is not None:
            preview = str(task["result"])
            if len(preview) > 500:
                preview = preview[:500] + "..."
            response += f"- Result: {preview}\n"
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
