"""
Main schedule generator.

This module is the entry point for schedule generation.
It delegates to the constraint-based engine for optimal scheduling.
"""

from .models import ScheduleRequest, ScheduleResponse
from .constraint_engine import generate_schedule as generate_schedule_constraint


def generate_schedule(request: ScheduleRequest) -> ScheduleResponse:
    """
    Generate a study schedule for the given date range.

    Uses OR-Tools CP-SAT solver for constraint-based optimization.

    Hard constraints:
        - Daily study time limits (respects study_hours setting)
        - Exam topics MUST be completed before their exam date
        - No scheduling on or after exam date for exam topics

    Soft constraints (optimized):
        - Complete non-exam topics by semester end
        - Avoid cramming (prefer earlier scheduling)
        - Prioritize by exam urgency (weight / days until)

    Args:
        request: The schedule generation request with topics, assessments, etc.

    Returns:
        ScheduleResponse with daily plans

    Raises:
        ValueError: If constraints cannot be satisfied (not enough time)
    """
    return generate_schedule_constraint(request)
