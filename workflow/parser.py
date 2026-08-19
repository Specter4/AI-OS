"""
Task Parser

Converts an AI-generated plan into Task objects.
"""

import re

from core.tasks import Task
from core.logger import log


VALID_AGENTS = {
    "assistant",
    "research",
    "browser",
    "planner",
    "content",
    "design",
    "coding",
    "review",
}


def parse_plan(plan: str):

    tasks = []

    lines = plan.splitlines()

    task_id = 1

    for line in lines:

        line = line.strip()

        if not line:
            continue

        # --------------------------------------------------
        # Match numbered tasks
        # --------------------------------------------------

        match = re.match(
            r"^(\d+[\.\)]\s*)(.+)$",
            line
        )

        if not match:
            continue

        content = match.group(2).strip()

        # --------------------------------------------------
        # Extract dependency information
        # --------------------------------------------------

        depends_on = []

        dependency_match = re.search(
            r"\|\s*depends:\s*([^|]+)$",
            content,
            re.IGNORECASE
        )

        if dependency_match:

            dependency_text = (
                dependency_match.group(1)
                .strip()
                .lower()
            )

            if dependency_text != "none":

                for value in dependency_text.split(","):

                    value = value.strip()

                    if value.isdigit():

                        depends_on.append(
                            int(value)
                        )

            # Remove dependency section
            content = content[
                :dependency_match.start()
            ].strip()

        # --------------------------------------------------
        # Extract agent
        # --------------------------------------------------

        if "|" in content:

            title, agent = content.rsplit("|", 1)

            title = title.strip()

            agent = agent.strip().lower()

        else:

            title = content

            agent = detect_agent(title)

        # --------------------------------------------------
        # Validate agent
        # --------------------------------------------------

        if agent not in VALID_AGENTS:

            log(
                f"Unknown agent '{agent}' for task: "
                f"{title}. Falling back to assistant."
            )

            agent = "assistant"

        # --------------------------------------------------
        # Create task
        # --------------------------------------------------

        task = Task(
            id=task_id,
            title=title,
            agent=agent,
            depends_on=depends_on
        )

        tasks.append(task)

        log(
            f"Parsed Task {task_id}: "
            f"{title} -> {agent}"
            f" | depends: "
            f"{depends_on if depends_on else 'none'}"
        )

        task_id += 1

    if not tasks:

        log(
            "Parser could not find any executable tasks."
        )

    return tasks


def detect_agent(title: str):

    lower = title.lower()

    if any(word in lower for word in [
        "open website",
        "visit website",
        "visit",
        "browse",
        "browser",
        "navigate",
        "webpage",
        "website",
        "search web",
        "google",
        "click",
        "login",
        "log in",
        "sign up",
        "signup",
        "create account"
    ]):

        return "browser"

    if any(word in lower for word in [
        "research",
        "analyze",
        "analysis",
        "investigate",
        "compare",
        "competitor",
        "collect information",
        "gather information"
    ]):

        return "research"

    if any(word in lower for word in [
        "copy",
        "content",
        "write",
        "article",
        "blog",
        "email",
        "script"
    ]):

        return "content"

    if any(word in lower for word in [
        "design",
        "ui",
        "ux",
        "interface",
        "layout",
        "visual"
    ]):

        return "design"

    if any(word in lower for word in [
        "frontend",
        "backend",
        "code",
        "coding",
        "develop",
        "program",
        "implement",
        "build"
    ]):

        return "coding"

    if any(word in lower for word in [
        "review",
        "test",
        "testing",
        "qa",
        "debug",
        "check"
    ]):

        return "review"

    if any(word in lower for word in [
        "plan",
        "planning",
        "sitemap",
        "workflow",
        "organize"
    ]):

        return "planner"

    return "assistant"