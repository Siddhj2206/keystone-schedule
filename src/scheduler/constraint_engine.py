"""
Constraint-based scheduler using OR-Tools CP-SAT solver.

This replaces the NumPy heuristic engine with a proper constraint
satisfaction solver that guarantees:
1. Hard constraints are ALWAYS satisfied
2. Soft constraints are optimized
3. Infeasible schedules are detected and reported
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
from ortools.sat.python import cp_model

from .models import (
    Assessment,
    DailyPlan,
    ScheduleRequest,
    ScheduleResponse,
    SessionType,
    StudyTask,
    Topic,
    TopicStatus,
)


# =============================================================================
# Preprocessed Data Structure
# =============================================================================


# Maximum days to schedule at once (for performance)
MAX_SCHEDULING_WINDOW = 14


@dataclass
class PreprocessedData:
    """Data prepared for the solver."""

    topics: list[Topic]
    assessments: list[Assessment]

    n_days: int  # Full semester length (for deadline/urgency calculations)
    scheduling_window: int  # Days we actually schedule (max 14 for performance)
    n_topics: int

    # Arrays (NumPy for speed)
    available_minutes: np.ndarray  # (scheduling_window,) - study time per day
    topic_deadline: (
        np.ndarray
    )  # (n_topics,) - day index of earliest exam (relative to full range)
    topic_urgency: np.ndarray  # (n_topics,) - urgency score for objective
    required_time: np.ndarray  # (n_topics,) - minutes needed to complete
    topic_has_exam: np.ndarray  # (n_topics,) - bool, has upcoming exam

    # Mappings
    topic_id_to_idx: dict[str, int]
    dates: list[date]  # (scheduling_window,) - actual dates we schedule

    # Config
    min_session: int
    max_session: int


# =============================================================================
# Data Preprocessing
# =============================================================================


def preprocess_data(request: ScheduleRequest) -> PreprocessedData:
    """
    Convert request to solver-friendly format.

    - Filter completed topics
    - Filter needs_revision topics without exams
    - Filter past assessments
    - Build topic-to-deadline mapping
    - Calculate required time per topic
    - Limit scheduling window to MAX_SCHEDULING_WINDOW days for performance
    """
    # Parse dates (YYYY-MM-DD format, no timezone issues)
    start = date.fromisoformat(request.start_date)
    end = date.fromisoformat(request.end_date)
    n_days = (end - start).days + 1  # Full semester length

    # Limit scheduling window for performance (solver complexity grows with days)
    scheduling_window = min(MAX_SCHEDULING_WINDOW, n_days)

    # Filter assessments first: only future ones (relative to start_date)
    start_ms = int(datetime.combine(start, datetime.min.time()).timestamp() * 1000)
    assessments = [a for a in request.assessments if a.date > start_ms]

    # Build set of topic IDs that have upcoming exams
    topics_with_exams = set()
    for a in assessments:
        topics_with_exams.update(a.topic_ids)

    # Filter topics:
    # - pending: always include (need to learn)
    # - needs_revision: only if has upcoming exam (revision without exam is pointless)
    # - completed: exclude
    topics = [
        t
        for t in request.topics
        if t.status == TopicStatus.pending
        or (t.status == TopicStatus.needs_revision and t.id in topics_with_exams)
    ]
    n_topics = len(topics)

    # Build topic ID -> index mapping
    topic_id_to_idx = {t.id: i for i, t in enumerate(topics)}

    # Build day array - ONLY for scheduling_window days (not full semester)
    available_minutes = np.zeros(scheduling_window, dtype=np.int32)
    dates_list: list[date] = []

    for i in range(scheduling_window):
        day = start + timedelta(days=i)
        dates_list.append(day)
        # Convert Python weekday (Mon=0) to JS weekday (Sun=0)
        js_weekday = (day.weekday() + 1) % 7
        available_minutes[i] = request.study_hours.get(js_weekday, 120)

    # Topic deadlines and urgency
    # deadline = day index of earliest exam (n_days if no exam = soft deadline at end)
    # urgency = weightage / days_until for objective weighting
    topic_deadline = np.full(n_topics, n_days, dtype=np.int32)
    topic_urgency = np.zeros(n_topics, dtype=np.float64)
    topic_has_exam = np.zeros(n_topics, dtype=bool)

    for a in assessments:
        # Convert exam timestamp to day index
        exam_date = date.fromtimestamp(a.date / 1000)
        exam_day_idx = (exam_date - start).days

        # Skip if exam is before our range or after
        if exam_day_idx < 0 or exam_day_idx > n_days:
            continue

        for topic_id in a.topic_ids:
            if topic_id in topic_id_to_idx:
                idx = topic_id_to_idx[topic_id]
                topic_has_exam[idx] = True

                # Track earliest exam deadline
                if exam_day_idx < topic_deadline[idx]:
                    topic_deadline[idx] = exam_day_idx

                # Urgency = weightage / days_until (higher = more urgent)
                days_until = max(1, exam_day_idx)
                new_urgency = a.weightage / days_until
                if new_urgency > topic_urgency[idx]:
                    topic_urgency[idx] = new_urgency

    # Non-exam topics: priority by sort_order (lower sort_order = earlier in syllabus = higher priority)
    max_sort_order = max((t.sort_order for t in topics), default=0)
    for i in range(n_topics):
        if not topic_has_exam[i]:
            # Invert sort_order: lower sort_order → higher urgency
            # Scale to 0.01-0.09 range (below exam urgency which is typically >= 1)
            if max_sort_order > 0:
                normalized = (max_sort_order - topics[i].sort_order) / max_sort_order
            else:
                normalized = 1.0
            topic_urgency[i] = 0.01 + normalized * 0.08

    # Required time per topic: est_minutes * (1.5 - mastery)
    # This means 0% mastery = 1.5x time, 100% mastery = 0.5x time
    required_time = np.array(
        [int(t.est_minutes * (1.5 - t.current_mastery)) for t in topics],
        dtype=np.int32,
    )

    return PreprocessedData(
        topics=topics,
        assessments=assessments,
        n_days=n_days,
        scheduling_window=scheduling_window,
        n_topics=n_topics,
        available_minutes=available_minutes,
        topic_deadline=topic_deadline,
        topic_urgency=topic_urgency,
        required_time=required_time,
        topic_has_exam=topic_has_exam,
        topic_id_to_idx=topic_id_to_idx,
        dates=dates_list,
        min_session=request.session_preferences.min_minutes,
        max_session=request.session_preferences.max_minutes,
    )


# =============================================================================
# OR-Tools CP-SAT Model Builder
# =============================================================================


def build_model(
    data: PreprocessedData,
) -> tuple[cp_model.CpModel, dict[tuple[int, int], cp_model.IntVar]]:
    """
    Build the constraint satisfaction model.

    Decision variables:
        task[t, d] = minutes allocated to topic t on day d (only for scheduling_window days)

    Hard constraints:
        1. Daily limit: sum(task[*, d]) <= available[d]
        2. Topic completion before exam: sum(task[t, d] for d < deadline) >= required[t]
           (only enforced if deadline is within scheduling_window)
        3. No scheduling after exam: task[t, d] = 0 for d >= deadline[t]
        4. Session bounds: task[t, d] in {0} ∪ [min_session, max_session]

    Soft constraints (in objective):
        - Complete all topics (including non-exam) by semester end
        - Prefer earlier scheduling (avoid cramming)
        - Weight by urgency (exam topics prioritized)
    """
    model = cp_model.CpModel()

    n_topics = data.n_topics
    scheduling_window = data.scheduling_window  # Use scheduling_window, not n_days
    max_session = data.max_session
    min_session = data.min_session

    # ==========================================================================
    # DECISION VARIABLES (only for scheduling_window days)
    # ==========================================================================

    # task[t, d] = minutes allocated to topic t on day d
    tasks: dict[tuple[int, int], cp_model.IntVar] = {}
    for t in range(n_topics):
        for d in range(scheduling_window):
            tasks[t, d] = model.NewIntVar(0, max_session, f"task_{t}_{d}")

    # scheduled[t, d] = 1 if topic t is scheduled on day d
    scheduled: dict[tuple[int, int], cp_model.IntVar] = {}
    for t in range(n_topics):
        for d in range(scheduling_window):
            scheduled[t, d] = model.NewBoolVar(f"sched_{t}_{d}")

    # Link task and scheduled variables
    for t in range(n_topics):
        for d in range(scheduling_window):
            # If scheduled, task must be >= min_session
            model.Add(tasks[t, d] >= min_session).OnlyEnforceIf(scheduled[t, d])
            # If not scheduled, task must be 0
            model.Add(tasks[t, d] == 0).OnlyEnforceIf(scheduled[t, d].Not())

    # ==========================================================================
    # HARD CONSTRAINTS
    # ==========================================================================

    # 1. Daily time limit - never exceed available study time
    for d in range(scheduling_window):
        model.Add(
            sum(tasks[t, d] for t in range(n_topics)) <= int(data.available_minutes[d])
        )

    # 2. Exam topics must be completed before their deadline
    #    ONLY enforce if deadline is within scheduling_window
    for t in range(n_topics):
        deadline = int(data.topic_deadline[t])
        required = int(data.required_time[t])

        if deadline <= scheduling_window and data.topic_has_exam[t]:
            # Has exam within window - MUST complete before deadline
            model.Add(
                sum(tasks[t, d] for d in range(min(deadline, scheduling_window)))
                >= required
            )

    # 3. No scheduling on or after exam day for exam topics (within window)
    for t in range(n_topics):
        deadline = int(data.topic_deadline[t])
        if deadline < scheduling_window and data.topic_has_exam[t]:
            # Has exam within window - cannot schedule on/after exam day
            for d in range(deadline, scheduling_window):
                model.Add(tasks[t, d] == 0)

    # 4. Don't over-study: total time per topic <= required time
    # This prevents the solver from dumping extra time into high-urgency topics
    for t in range(n_topics):
        required = int(data.required_time[t])
        model.Add(sum(tasks[t, d] for d in range(scheduling_window)) <= required)

    # ==========================================================================
    # OBJECTIVE (SOFT CONSTRAINTS)
    # ==========================================================================

    # We want to:
    # 1. Complete as many topics as possible (especially non-exam topics)
    # 2. Prioritize urgent (exam) topics
    # 3. Prefer scheduling earlier rather than cramming

    objective_terms = []

    for t in range(n_topics):
        # Scale urgency to integer (CP-SAT works with integers)
        urgency_weight = int(data.topic_urgency[t] * 1000) + 1
        deadline = int(data.topic_deadline[t])

        for d in range(scheduling_window):
            # Skip days after deadline (already constrained to 0)
            if (
                d >= deadline
                and deadline < scheduling_window
                and data.topic_has_exam[t]
            ):
                continue

            # Early day bonus: prefer not cramming
            # Days closer to start get higher weight
            early_bonus = (scheduling_window - d) * 10 // scheduling_window + 1

            # Combined weight
            weight = urgency_weight * early_bonus

            objective_terms.append(weight * tasks[t, d])

    # For non-exam topics, add soft incentive to complete them
    for t in range(n_topics):
        if not data.topic_has_exam[t]:
            # Non-exam topic - add bonus for completion
            required = int(data.required_time[t])
            total_scheduled = sum(tasks[t, d] for d in range(scheduling_window))

            # Create a boolean: did we complete this topic?
            completed = model.NewBoolVar(f"completed_{t}")
            model.Add(total_scheduled >= required).OnlyEnforceIf(completed)
            model.Add(total_scheduled < required).OnlyEnforceIf(completed.Not())

            # Add completion bonus to objective
            completion_bonus = 500  # Encourage completing all topics
            objective_terms.append(completion_bonus * completed)

    model.Maximize(sum(objective_terms))

    return model, tasks


# =============================================================================
# Solver
# =============================================================================


def solve_and_extract(
    model: cp_model.CpModel,
    tasks: dict[tuple[int, int], cp_model.IntVar],
    data: PreprocessedData,
) -> ScheduleResponse:
    """
    Solve the model and extract the schedule.
    """
    solver = cp_model.CpSolver()

    # Timeout - find a good solution quickly, don't wait for optimal
    solver.parameters.max_time_in_seconds = 10

    # Use fewer cores to avoid maxing out CPU
    solver.parameters.num_search_workers = 4

    # Solve
    status = solver.Solve(model)

    if status == cp_model.INFEASIBLE:
        raise ValueError(
            "Cannot create feasible schedule - not enough time to complete all exam topics"
        )

    if status == cp_model.MODEL_INVALID:
        raise ValueError("Invalid model - this is a bug in the scheduler")

    # OPTIMAL or FEASIBLE - extract solution
    daily_plans: list[DailyPlan] = []
    topics_with_tasks: set[str] = set()
    total_study_minutes = 0

    for d in range(data.scheduling_window):
        tasks_today: list[StudyTask] = []

        for t in range(data.n_topics):
            minutes = solver.Value(tasks[t, d])
            if minutes > 0:
                topic = data.topics[t]

                # Determine session type based on topic status
                # needs_revision = revision session, pending = learning session
                session_type = (
                    SessionType.revision
                    if topic.status == TopicStatus.needs_revision
                    else SessionType.learning
                )

                tasks_today.append(
                    StudyTask(
                        topic_id=topic.id,
                        topic_title=topic.title,
                        subject_id=topic.subject_id,
                        duration_minutes=minutes,
                        session_type=session_type,
                        priority_score=round(float(data.topic_urgency[t]), 2),
                    )
                )
                topics_with_tasks.add(topic.id)
                total_study_minutes += minutes

        # Sort tasks by priority (highest first)
        tasks_today.sort(key=lambda x: -x.priority_score)

        daily_plans.append(
            DailyPlan(
                date=data.dates[d].isoformat(),
                tasks=tasks_today,
                total_minutes=sum(t.duration_minutes for t in tasks_today),
                available_minutes=int(data.available_minutes[d]),
            )
        )

    return ScheduleResponse(
        daily_plans=daily_plans,
        total_days=data.scheduling_window,
        total_study_minutes=total_study_minutes,
        topics_covered=len(topics_with_tasks),
    )


# =============================================================================
# Main Entry Point
# =============================================================================


def generate_schedule(request: ScheduleRequest) -> ScheduleResponse:
    """
    Generate a study schedule using constraint programming.

    This function:
    1. Preprocesses the request (filters, computes deadlines)
    2. Builds a CP-SAT model with hard and soft constraints
    3. Solves the model
    4. Extracts and returns the schedule

    Hard constraints enforced:
    - Daily study time limits
    - Exam topics completed before exam date
    - No scheduling after exam date

    Soft constraints optimized:
    - Complete non-exam topics by semester end
    - Prefer earlier scheduling (avoid cramming)
    - Prioritize by exam urgency
    """
    # Handle empty case
    incomplete = [t for t in request.topics if t.status != TopicStatus.completed]
    if not incomplete:
        return ScheduleResponse(
            daily_plans=[],
            total_days=0,
            total_study_minutes=0,
            topics_covered=0,
        )

    # Preprocess
    data = preprocess_data(request)

    if data.n_topics == 0:
        return ScheduleResponse(
            daily_plans=[],
            total_days=0,
            total_study_minutes=0,
            topics_covered=0,
        )

    # Build and solve model
    model, tasks = build_model(data)
    return solve_and_extract(model, tasks, data)
