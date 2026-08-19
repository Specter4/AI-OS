"""
Planner Agent

Creates an execution plan using AI.
"""

from core.logger import log

from agents.planner_ai import create_plan

from workflow.parser import parse_plan


def plan(goal: str):

    log(f"Planning goal: {goal}")

    ai_plan = create_plan(goal)

    log("AI generated plan.")

    tasks = parse_plan(ai_plan)

    return tasks