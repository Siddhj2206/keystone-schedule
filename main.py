"""
FastAPI server for the schedule generation service.

This service receives schedule generation requests from the main backend
and returns optimized study plans.

Run with: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.scheduler.models import ScheduleRequest, ScheduleResponse
from src.scheduler.generator import generate_schedule

app = FastAPI(
    title="Keystone Schedule Generator",
    description="AI-powered study schedule generation service",
    version="0.1.0",
)

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "keystone-schedule"}


@app.post("/generate", response_model=ScheduleResponse)
async def generate_schedule_endpoint(request: ScheduleRequest) -> ScheduleResponse:
    """
    Generate a study schedule based on the provided topics, assessments, and preferences.

    This is the main endpoint called by the Keystone backend.

    Args:
        request: ScheduleRequest containing:
            - topics: List of topics to schedule
            - assessments: Upcoming exams/quizzes
            - study_hours: Available hours per day of week
            - session_preferences: Min/max session length
            - start_date, end_date: Date range to schedule
            - recent_study_time: Optional, for balance calculation

    Returns:
        ScheduleResponse with daily study plans
    """
    try:
        # Validate we have topics to schedule
        if not request.topics:
            raise HTTPException(
                status_code=400, detail="No topics provided to schedule"
            )

        # Validate date range
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=400, detail="start_date must be before or equal to end_date"
            )

        # Generate the schedule
        result = generate_schedule(request)

        return result

    except HTTPException:
        raise
    except Exception as e:
        # Log the error in production
        raise HTTPException(
            status_code=500, detail=f"Schedule generation failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Keystone Schedule Generator",
        "version": "0.1.0",
        "endpoints": {
            "POST /generate": "Generate a study schedule",
            "GET /health": "Health check",
        },
    }
