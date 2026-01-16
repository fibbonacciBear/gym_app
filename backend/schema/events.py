"""Event type definitions and validation."""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime

class EventType(str, Enum):
    """All supported event types."""
    WORKOUT_STARTED = "WorkoutStarted"
    WORKOUT_COMPLETED = "WorkoutCompleted"
    WORKOUT_DISCARDED = "WorkoutDiscarded"
    EXERCISE_ADDED = "ExerciseAdded"
    SET_LOGGED = "SetLogged"
    SET_MODIFIED = "SetModified"
    SET_DELETED = "SetDeleted"
    TEMPLATE_CREATED = "TemplateCreated"
    TEMPLATE_UPDATED = "TemplateUpdated"
    TEMPLATE_DELETED = "TemplateDeleted"

class WeightUnit(str, Enum):
    KG = "kg"
    LB = "lb"

# Set group for advanced workout programming
class SetGroup(BaseModel):
    target_sets: int
    target_reps: Optional[int] = None
    target_weight: Optional[float] = None
    target_unit: str = "kg"
    set_type: str = "working"  # warmup, working, dropset, pyramid, other
    rest_seconds: int = 60
    notes: Optional[str] = None


# Exercise plan for guided workouts (from templates)
class ExercisePlan(BaseModel):
    exercise_id: str
    # NEW: set groups (takes precedence if present)
    set_groups: Optional[List[SetGroup]] = None
    # OLD: single-target fields (for backward compatibility)
    target_sets: Optional[int] = None
    target_reps: Optional[int] = None
    target_weight: Optional[float] = None
    target_unit: str = "kg"
    set_type: str = "standard"
    rest_seconds: int = 60
    notes: Optional[str] = None

# Payload models for each event type
class WorkoutStartedPayload(BaseModel):
    workout_id: str = Field(default_factory=lambda: str(uuid4()))
    name: Optional[str] = None
    from_template_id: Optional[str] = None
    exercise_ids: Optional[List[str]] = None
    exercise_plans: Optional[List[ExercisePlan]] = None  # For guided workouts

class WorkoutCompletedPayload(BaseModel):
    workout_id: str
    notes: Optional[str] = None

class WorkoutDiscardedPayload(BaseModel):
    workout_id: str
    reason: Optional[str] = None

class ExerciseAddedPayload(BaseModel):
    workout_id: str
    exercise_id: str

class SetLoggedPayload(BaseModel):
    workout_id: str
    exercise_id: str
    weight: float = Field(gt=0)
    reps: int = Field(gt=0)
    unit: WeightUnit = WeightUnit.KG

class SetModifiedPayload(BaseModel):
    workout_id: str
    original_event_id: str
    weight: Optional[float] = Field(default=None, gt=0)
    reps: Optional[int] = Field(default=None, gt=0)
    unit: Optional[WeightUnit] = None

class SetDeletedPayload(BaseModel):
    workout_id: str
    original_event_id: str
    reason: Optional[str] = None

class SetType(str, Enum):
    """Type of set."""
    STANDARD = "standard"
    AMRAP = "amrap"  # As Many Reps As Possible
    DROP = "drop"     # Drop set
    WARMUP = "warmup"


class TemplateExercise(BaseModel):
    """Exercise within a template with target values."""
    exercise_id: str
    # NEW: set groups (takes precedence if present)
    set_groups: Optional[List[SetGroup]] = None
    # OLD: single-target fields (for backward compatibility)
    target_sets: Optional[int] = Field(default=None, ge=1)
    target_reps: Optional[int] = Field(default=None, ge=1)
    target_weight: Optional[float] = Field(default=None, ge=0)
    target_unit: WeightUnit = WeightUnit.KG
    set_type: SetType = SetType.STANDARD
    rest_seconds: int = Field(default=60, ge=0)
    notes: Optional[str] = None


class TemplateCreatedPayload(BaseModel):
    template_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    # Support both legacy (exercise_ids) and new (exercises) format
    exercise_ids: Optional[List[str]] = None  # Legacy: just IDs
    exercises: Optional[List[TemplateExercise]] = None  # New: full exercise specs
    source_workout_id: Optional[str] = None


class TemplateUpdatedPayload(BaseModel):
    template_id: str
    name: Optional[str] = None
    exercise_ids: Optional[List[str]] = None  # Legacy
    exercises: Optional[List[TemplateExercise]] = None  # New


class TemplateDeletedPayload(BaseModel):
    template_id: str

# Map event types to payload models
PAYLOAD_MODELS = {
    EventType.WORKOUT_STARTED: WorkoutStartedPayload,
    EventType.WORKOUT_COMPLETED: WorkoutCompletedPayload,
    EventType.WORKOUT_DISCARDED: WorkoutDiscardedPayload,
    EventType.EXERCISE_ADDED: ExerciseAddedPayload,
    EventType.SET_LOGGED: SetLoggedPayload,
    EventType.SET_MODIFIED: SetModifiedPayload,
    EventType.SET_DELETED: SetDeletedPayload,
    EventType.TEMPLATE_CREATED: TemplateCreatedPayload,
    EventType.TEMPLATE_UPDATED: TemplateUpdatedPayload,
    EventType.TEMPLATE_DELETED: TemplateDeletedPayload,
}

def validate_payload(event_type: EventType, payload: Dict[str, Any]) -> BaseModel:
    """Validate payload against schema for event type."""
    model_class = PAYLOAD_MODELS.get(event_type)
    if not model_class:
        raise ValueError(f"Unknown event type: {event_type}")
    return model_class(**payload)
