"""Workout history endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from backend.database import get_projection

router = APIRouter(prefix="/api/history", tags=["history"])

# Conversion factor: 1 lb = 0.453592 kg
LB_TO_KG = 0.453592

def backfill_stats(workout: Dict[str, Any]) -> Dict[str, Any]:
    """Add stats and fix missing fields for pre-Sprint 2/3 workouts."""
    # Fix missing timestamps (use empty string for workouts that lack them)
    if not workout.get("started_at"):
        workout["started_at"] = ""
    if not workout.get("completed_at"):
        workout["completed_at"] = ""

    # Fix missing event_id in sets (pre-Sprint 2)
    for exercise in workout.get("exercises", []):
        for set_data in exercise.get("sets", []):
            if "event_id" not in set_data:
                # Use placeholder for old sets
                set_data["event_id"] = "legacy"

    # Calculate stats if missing (pre-Sprint 3)
    if "stats" not in workout:
        exercises = workout.get("exercises", [])
        total_sets = sum(len(e.get("sets", [])) for e in exercises)

        # Calculate volume with unit normalization
        total_volume_kg = 0.0
        for exercise in exercises:
            for set_data in exercise.get("sets", []):
                weight = set_data.get("weight", 0)
                reps = set_data.get("reps", 0)
                unit = set_data.get("unit", "kg")

                # Normalize to kg
                weight_kg = weight if unit == "kg" else weight * LB_TO_KG
                total_volume_kg += weight_kg * reps

        workout["stats"] = {
            "exercise_count": len(exercises),
            "total_sets": total_sets,
            "total_volume": total_volume_kg
        }

    return workout

class WorkoutStats(BaseModel):
    exercise_count: int
    total_sets: int
    total_volume: float

class SetRecord(BaseModel):
    event_id: str
    weight: float
    reps: int
    unit: str

class ExerciseRecord(BaseModel):
    exercise_id: str
    sets: List[SetRecord]

class WorkoutHistoryEntry(BaseModel):
    id: str
    started_at: str
    completed_at: str
    exercises: List[ExerciseRecord]
    stats: WorkoutStats
    notes: Optional[str] = ""
    from_template_id: Optional[str] = None

@router.get("", response_model=List[WorkoutHistoryEntry])
async def list_workout_history(limit: int = 50):
    """Get workout history, most recent first."""
    history = get_projection("workout_history", "default") or []
    # Backfill stats for pre-Sprint 3 workouts
    history_with_stats = [backfill_stats(w) for w in history]
    return history_with_stats[:limit]

@router.get("/{workout_id}", response_model=WorkoutHistoryEntry)
async def get_workout_detail(workout_id: str):
    """Get a specific workout from history."""
    history = get_projection("workout_history", "default") or []
    workout = next((w for w in history if w["id"] == workout_id), None)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    # Backfill stats if missing
    return backfill_stats(workout)
