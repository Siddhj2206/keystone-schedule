"""
Data models for the schedule generator.

These models define the contract between the backend API and this service.
They match the TypeScript types in keystone-backend/src/lib/types.ts
"""

from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================


class TopicStatus(str, Enum):
    """
    Status of a topic in the syllabus.

    - pending: Not started yet
    - completed: Fully mastered
    - needs_revision: Studied but needs reinforcement
    """

    pending = "pending"
    completed = "completed"
    needs_revision = "needs_revision"


class SessionType(str, Enum):
    """
    Type of study session.

    - learning: First time studying the topic
    - revision: Reviewing previously studied material
    """

    learning = "learning"
    revision = "revision"


# =============================================================================
# Input Models (what we receive from the backend)
# =============================================================================


class Topic(BaseModel):
    """
    A single topic/chapter in the syllabus.

    This is the atomic unit we schedule study sessions for.
    """

    id: str
    subject_id: str
    title: str
    est_minutes: int = Field(ge=1, description="Estimated time to learn this topic")
    current_mastery: float = Field(
        ge=0, le=1, description="0.0 = not started, 1.0 = fully mastered"
    )
    status: TopicStatus
    sort_order: int = Field(
        default=0, description="Order in syllabus (lower = earlier)"
    )

    # Optional: for tracking when topic was last studied
    last_studied_at: Optional[int] = Field(
        default=None, description="Unix timestamp ms"
    )


class Assessment(BaseModel):
    """
    An upcoming exam, quiz, or assignment.

    Assessments drive urgency - topics linked to upcoming assessments
    get higher priority.
    """

    id: str
    subject_id: str
    title: str
    date: int = Field(description="Unix timestamp ms")
    weightage: int = Field(
        ge=0, le=100, description="How much this counts toward final grade"
    )
    topic_ids: list[str] = Field(
        default_factory=list, description="Topics covered by this assessment"
    )


class SubjectStudyTime(BaseModel):
    """
    Tracks how much time has been spent on each subject recently.

    Used for balancing - if a subject has been neglected, its topics
    get a priority boost.
    """

    subject_id: str
    minutes_studied: int = Field(ge=0, description="Total minutes in recent period")


class SessionPreferences(BaseModel):
    """
    User preferences for study session length.

    These come from user settings - some people prefer short Pomodoro
    sessions, others prefer longer deep work blocks.
    """

    min_minutes: int = Field(
        default=25, ge=5, le=60, description="Minimum session length"
    )
    max_minutes: int = Field(
        default=60, ge=15, le=180, description="Maximum session length"
    )


# Type alias for study hours - dict mapping day of week (0-6) to minutes
StudyHoursDict = dict[int, int]


class ScheduleRequest(BaseModel):
    """
    The complete request to generate a schedule.

    This is what the backend sends to us when the user clicks
    "Generate Schedule" or when triggered automatically.
    """

    # Core data
    topics: list[Topic]
    assessments: list[Assessment] = Field(default_factory=list)

    # Configuration
    # study_hours: dict mapping day of week (0=Sunday, 6=Saturday) to minutes
    # Example: {0: 60, 1: 120, 2: 120, 3: 120, 4: 120, 5: 120, 6: 60}
    study_hours: StudyHoursDict = Field(
        default_factory=lambda: {i: 120 if 1 <= i <= 5 else 60 for i in range(7)}
    )
    session_preferences: SessionPreferences = Field(default_factory=SessionPreferences)

    # Time range to schedule
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    end_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")

    # Optional: for balance calculation
    recent_study_time: list[SubjectStudyTime] = Field(default_factory=list)

    @field_validator("study_hours")
    @classmethod
    def validate_study_hours(cls, v: StudyHoursDict) -> StudyHoursDict:
        """Ensure all days 0-6 are present and values are non-negative."""
        for day in range(7):
            if day not in v:
                # Default: 60 min on weekends, 120 min on weekdays
                v[day] = 60 if day in (0, 6) else 120
            if v[day] < 0:
                raise ValueError(f"Study hours for day {day} cannot be negative")
        return v


# =============================================================================
# Output Models (what we return to the backend)
# =============================================================================


class StudyTask(BaseModel):
    """
    A single study task for a day.

    NOT a fixed time slot - just "study this topic for X minutes today".
    The student decides when to fit it in.
    """

    topic_id: str
    topic_title: str
    subject_id: str
    duration_minutes: int = Field(ge=1, description="How long to study")
    session_type: SessionType
    priority_score: float = Field(
        description="Why this topic was chosen (for debugging)"
    )


class DailyPlan(BaseModel):
    """
    The study plan for a single day.

    Contains a list of tasks to complete, in priority order.
    Total duration should not exceed the day's available study hours.
    """

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    tasks: list[StudyTask]
    total_minutes: int = Field(description="Sum of all task durations")
    available_minutes: int = Field(description="Study hours available this day")


class ScheduleResponse(BaseModel):
    """
    The complete response from the schedule generator.

    Contains a daily breakdown of what to study.
    """

    daily_plans: list[DailyPlan]

    # Summary stats for the frontend
    total_days: int
    total_study_minutes: int
    topics_covered: int  # Unique topics with at least one session
