"""Event handling and processing."""
from typing import Dict, Any, Optional, Tuple
from uuid import uuid4

from backend.database import append_event, get_projection, set_projection
from backend.schema.events import (
    EventType,
    validate_payload,
    WorkoutStartedPayload,
    WorkoutCompletedPayload,
)

def emit_event(
    event_type: EventType,
    payload: Dict[str, Any],
    user_id: str = "default"
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Emit an event: validate, store, and update projections.

    Returns:
        Tuple of (event_record, derived_data)
    """
    # Validate payload
    validated = validate_payload(event_type, payload)
    validated_dict = validated.model_dump()

    # Generate event ID
    event_id = str(uuid4())

    # Store event
    event_record = append_event(
        event_id=event_id,
        event_type=event_type.value,
        payload=validated_dict,
        user_id=user_id
    )

    # Update projections based on event type
    derived = update_projections(event_type, validated_dict, user_id)

    return event_record, derived

def update_projections(
    event_type: EventType,
    payload: Dict[str, Any],
    user_id: str
) -> Optional[Dict[str, Any]]:
    """Update projections based on event. Returns derived data."""
    derived = {}

    if event_type == EventType.WORKOUT_STARTED:
        from datetime import datetime
        # Create current_workout projection
        workout_id = payload.get("workout_id")
        current_workout = {
            "id": workout_id,
            "started_at": datetime.utcnow().isoformat() + "Z",
            "from_template_id": payload.get("from_template_id"),
            "focus_exercise": None,
            "exercises": []
        }

        # If starting from template with exercises, add them
        exercise_ids = payload.get("exercise_ids") or []
        for ex_id in exercise_ids:
            current_workout["exercises"].append({
                "exercise_id": ex_id,
                "sets": []
            })
        if exercise_ids:
            current_workout["focus_exercise"] = exercise_ids[0]

        set_projection("current_workout", current_workout, user_id)

    elif event_type == EventType.WORKOUT_COMPLETED:
        # Move current workout to history, clear current
        current = get_projection("current_workout", user_id)
        if current:
            from datetime import datetime
            # Add to workout history
            history = get_projection("workout_history", user_id) or []
            current["completed_at"] = datetime.utcnow().isoformat() + "Z"
            current["notes"] = payload.get("notes", "")
            history.insert(0, current)  # Most recent first
            set_projection("workout_history", history, user_id)

        # Clear current workout
        set_projection("current_workout", None, user_id)

    elif event_type == EventType.WORKOUT_DISCARDED:
        # Just clear current workout
        set_projection("current_workout", None, user_id)

    return derived if derived else None
