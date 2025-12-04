"""Event handling and processing."""
from typing import Dict, Any, Optional, Tuple
from uuid import uuid4
import sqlite3

from backend.database import append_event, get_projection, set_projection, get_connection
from backend.schema.events import (
    EventType,
    validate_payload,
    WorkoutStartedPayload,
    WorkoutCompletedPayload,
)

class ConcurrencyConflictError(Exception):
    """Raised when a database lock conflict occurs due to concurrent operations."""
    pass

def validate_event_preconditions(
    event_type: EventType,
    payload: Dict[str, Any],
    user_id: str,
    conn=None
) -> None:
    """
    Validate business logic preconditions before storing event.
    Raises ValueError if preconditions are not met.

    MUST be called within a transaction (with conn parameter) to prevent
    race conditions between validation and state changes.
    """
    # Helper to get projections using the provided connection (if any)
    def _get(key):
        return get_projection(key, user_id, conn)
    if event_type == EventType.WORKOUT_STARTED:
        # Prevent starting a workout when one is already active
        current = _get("current_workout")
        if current:
            raise ValueError("Cannot start workout: workout already in progress")

    elif event_type == EventType.EXERCISE_ADDED:
        # Validate active workout exists
        current = _get("current_workout")
        if not current:
            raise ValueError("Cannot add exercise: no active workout")

        # Validate workout_id matches
        if payload.get("workout_id") != current["id"]:
            raise ValueError(f"Event workout_id {payload.get('workout_id')} does not match current workout {current['id']}")

        # Check if exercise already in workout
        exercise_id = payload.get("exercise_id")
        existing = next((ex for ex in current["exercises"] if ex["exercise_id"] == exercise_id), None)
        if existing:
            raise ValueError(f"Exercise {exercise_id} already in workout")

    elif event_type == EventType.SET_LOGGED:
        # Validate active workout exists
        current = _get("current_workout")
        if not current:
            raise ValueError("Cannot log set: no active workout")

        # Validate workout_id matches
        if payload.get("workout_id") != current["id"]:
            raise ValueError(f"Event workout_id {payload.get('workout_id')} does not match current workout {current['id']}")

        # Validate exercise exists in workout (must be added via ExerciseAdded first)
        exercise_id = payload.get("exercise_id")
        exercise_exists = any(ex["exercise_id"] == exercise_id for ex in current["exercises"])
        if not exercise_exists:
            raise ValueError(f"Exercise {exercise_id} not in current workout. Add it with ExerciseAdded first.")

    elif event_type == EventType.SET_DELETED:
        # Validate active workout exists
        current = _get("current_workout")
        if not current:
            raise ValueError("Cannot delete set: no active workout")

        # Validate workout_id matches
        if payload.get("workout_id") != current["id"]:
            raise ValueError(f"Event workout_id {payload.get('workout_id')} does not match current workout {current['id']}")

        # Validate set exists
        original_event_id = payload.get("original_event_id")
        set_found = False
        for exercise in current["exercises"]:
            if any(s.get("event_id") == original_event_id for s in exercise["sets"]):
                set_found = True
                break

        if not set_found:
            raise ValueError(f"Set with event_id {original_event_id} not found in current workout")

    elif event_type == EventType.SET_MODIFIED:
        # Validate active workout exists
        current = _get("current_workout")
        if not current:
            raise ValueError("Cannot modify set: no active workout")

        # Validate workout_id matches
        if payload.get("workout_id") != current["id"]:
            raise ValueError(f"Event workout_id {payload.get('workout_id')} does not match current workout {current['id']}")

        # Validate set exists
        original_event_id = payload.get("original_event_id")
        set_found = False
        for exercise in current["exercises"]:
            if any(s.get("event_id") == original_event_id for s in exercise["sets"]):
                set_found = True
                break

        if not set_found:
            raise ValueError(f"Set with event_id {original_event_id} not found in current workout")

    elif event_type == EventType.TEMPLATE_CREATED:
        # Validate template doesn't already exist
        templates = _get("workout_templates") or []
        template_id = payload.get("template_id")

        template_exists = any(t["id"] == template_id for t in templates)
        if template_exists:
            raise ValueError(f"Template {template_id} already exists")

    elif event_type == EventType.TEMPLATE_UPDATED:
        # Validate template exists
        templates = _get("workout_templates") or []
        template_id = payload.get("template_id")

        template_found = any(t["id"] == template_id for t in templates)
        if not template_found:
            raise ValueError(f"Template {template_id} not found")

    elif event_type == EventType.TEMPLATE_DELETED:
        # Validate template exists
        templates = _get("workout_templates") or []
        template_id = payload.get("template_id")

        template_found = any(t["id"] == template_id for t in templates)
        if not template_found:
            raise ValueError(f"Template {template_id} not found")

    elif event_type == EventType.WORKOUT_COMPLETED:
        # Validate active workout exists and matches
        current = _get("current_workout")
        if not current:
            raise ValueError("Cannot complete workout: no active workout")

        if payload.get("workout_id") != current["id"]:
            raise ValueError(f"Event workout_id {payload.get('workout_id')} does not match current workout {current['id']}")

    elif event_type == EventType.WORKOUT_DISCARDED:
        # Validate active workout exists and matches
        current = _get("current_workout")
        if not current:
            raise ValueError("Cannot discard workout: no active workout")

        if payload.get("workout_id") != current["id"]:
            raise ValueError(f"Event workout_id {payload.get('workout_id')} does not match current workout {current['id']}")

def emit_event(
    event_type: EventType,
    payload: Dict[str, Any],
    user_id: str = "default"
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Emit an event: validate, store, and update projections.

    All operations happen within a single IMMEDIATE transaction that acquires
    a write lock before validation, preventing concurrent requests from both
    passing precondition checks.

    Returns:
        Tuple of (event_record, derived_data)

    Raises:
        ValueError: If preconditions fail
        ConcurrencyConflictError: If database is locked (concurrent operation)
    """
    # Validate payload schema
    validated = validate_payload(event_type, payload)
    validated_dict = validated.model_dump()

    # Generate event ID
    event_id = str(uuid4())

    # Execute validation, event storage, and projection updates in a single IMMEDIATE transaction
    # IMMEDIATE mode acquires write lock on BEGIN, preventing concurrent validation races
    try:
        with get_connection(user_id, isolation_level="IMMEDIATE") as conn:
            # Validate business preconditions INSIDE transaction (with write lock held)
            # This prevents double-start, double-finish, and other race conditions
            validate_event_preconditions(event_type, validated_dict, user_id, conn=conn)

            # Store event (within same transaction, after validation passes)
            event_record = append_event(
                event_id=event_id,
                event_type=event_type.value,
                payload=validated_dict,
                user_id=user_id,
                conn=conn
            )

            # Update projections (within same transaction)
            derived = update_projections(
                event_type,
                validated_dict,
                event_id,
                event_record["timestamp"],
                user_id,
                conn=conn
            )

            # Commit transaction (all or nothing)
            conn.commit()

        return event_record, derived
    except sqlite3.OperationalError as e:
        if "locked" in str(e).lower():
            # Database is locked - another transaction is in progress
            # Raise custom exception so API can return 409 Conflict (not 400/500)
            raise ConcurrencyConflictError(
                "Another operation is in progress. Please try again."
            ) from e
        raise

def update_projections(
    event_type: EventType,
    payload: Dict[str, Any],
    event_id: str,
    timestamp: str,
    user_id: str,
    conn=None
) -> Optional[Dict[str, Any]]:
    """Update projections based on event. Returns derived data."""
    derived = {}

    # Helper functions to use connection if provided
    def _get_projection(key):
        return get_projection(key, user_id, conn)

    def _set_projection(key, data):
        return set_projection(key, data, user_id, conn)

    if event_type == EventType.WORKOUT_STARTED:
        # Create current_workout projection (preconditions already validated)
        workout_id = payload.get("workout_id")
        current_workout = {
            "id": workout_id,
            "started_at": timestamp,
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

        _set_projection("current_workout", current_workout)

        # Track template usage
        from_template_id = payload.get("from_template_id")
        if from_template_id:
            templates = _get_projection("workout_templates") or []
            for template in templates:
                if template["id"] == from_template_id:
                    template["last_used_at"] = timestamp
                    template["use_count"] = template.get("use_count", 0) + 1
                    _set_projection("workout_templates", templates)
                    break

    elif event_type == EventType.WORKOUT_COMPLETED:
        # Move current workout to history, clear current
        current = _get_projection("current_workout")
        if current:
            # Calculate workout stats
            total_sets = sum(len(e["sets"]) for e in current["exercises"])

            # Calculate volume with unit normalization (1 lb = 0.453592 kg)
            total_volume_kg = 0.0
            for exercise in current["exercises"]:
                for set_data in exercise["sets"]:
                    weight = set_data.get("weight", 0)
                    reps = set_data.get("reps", 0)
                    unit = set_data.get("unit", "kg")
                    # Normalize to kg
                    weight_kg = weight if unit == "kg" else weight * 0.453592
                    total_volume_kg += weight_kg * reps

            # Create history entry with stats
            current["completed_at"] = timestamp
            current["notes"] = payload.get("notes", "")
            current["stats"] = {
                "exercise_count": len(current["exercises"]),
                "total_sets": total_sets,
                "total_volume": total_volume_kg
            }

            # Add to workout history
            history = _get_projection("workout_history") or []
            history.insert(0, current)  # Most recent first
            _set_projection("workout_history", history)

            # Set derived data
            derived["total_sets"] = total_sets
            derived["total_volume"] = total_volume_kg

        # Clear current workout
        _set_projection("current_workout", None)

    elif event_type == EventType.WORKOUT_DISCARDED:
        # Just clear current workout
        _set_projection("current_workout", None)

    elif event_type == EventType.EXERCISE_ADDED:
        # Add exercise to current workout (preconditions already validated)
        current = _get_projection("current_workout")
        if not current:
            # Should not happen due to preconditions, but defensive check for replay
            return derived
        exercise_id = payload.get("exercise_id")

        current["exercises"].append({
            "exercise_id": exercise_id,
            "sets": []
        })
        current["focus_exercise"] = exercise_id
        _set_projection("current_workout", current)

    elif event_type == EventType.SET_LOGGED:
        # Add set to exercise in current workout (preconditions already validated)
        current = _get_projection("current_workout")
        if not current:
            # Should not happen due to preconditions, but defensive check for replay
            return derived
        exercise_id = payload.get("exercise_id")

        # Find exercise (must exist due to precondition validation)
        exercise = next((ex for ex in current["exercises"] if ex["exercise_id"] == exercise_id), None)
        if not exercise:
            # Should not happen due to preconditions, but defensive check for replay
            return derived

        # Add the set with event_id for future edits/deletes
        exercise["sets"].append({
            "event_id": event_id,
            "weight": payload.get("weight"),
            "reps": payload.get("reps"),
            "unit": payload.get("unit")
        })

        # Update focus
        current["focus_exercise"] = exercise_id

        _set_projection("current_workout", current)

    elif event_type == EventType.SET_DELETED:
        # Remove set from current workout (preconditions already validated)
        current = _get_projection("current_workout")
        if not current:
            # Should not happen due to preconditions, but defensive check for replay
            return derived
        original_event_id = payload.get("original_event_id")

        # Find and remove the set with this event_id
        for exercise in current["exercises"]:
            original_length = len(exercise["sets"])
            exercise["sets"] = [s for s in exercise["sets"] if s.get("event_id") != original_event_id]

            # If we removed a set, update the projection
            if len(exercise["sets"]) < original_length:
                _set_projection("current_workout", current)
                break

    elif event_type == EventType.SET_MODIFIED:
        # Modify set in current workout (preconditions already validated)
        current = _get_projection("current_workout")
        if not current:
            # Should not happen due to preconditions, but defensive check for replay
            return derived
        original_event_id = payload.get("original_event_id")

        # Find and modify the set with this event_id
        set_modified = False
        for exercise in current["exercises"]:
            for set_obj in exercise["sets"]:
                if set_obj.get("event_id") == original_event_id:
                    # Update only the fields that are provided
                    if payload.get("weight") is not None:
                        set_obj["weight"] = payload.get("weight")
                    if payload.get("reps") is not None:
                        set_obj["reps"] = payload.get("reps")
                    if payload.get("unit") is not None:
                        set_obj["unit"] = payload.get("unit")
                    _set_projection("current_workout", current)
                    set_modified = True
                    break
            if set_modified:
                break

    elif event_type == EventType.TEMPLATE_CREATED:
        # Add template to workout_templates projection
        templates = _get_projection("workout_templates") or []
        template = {
            "id": payload.get("template_id"),
            "name": payload.get("name"),
            "exercise_ids": payload.get("exercise_ids"),
            "source_workout_id": payload.get("source_workout_id"),
            "created_at": timestamp,
            "last_used_at": None,
            "use_count": 0
        }
        templates.append(template)
        _set_projection("workout_templates", templates)

    elif event_type == EventType.TEMPLATE_UPDATED:
        # Update template in workout_templates projection
        templates = _get_projection("workout_templates") or []
        template_id = payload.get("template_id")

        for template in templates:
            if template["id"] == template_id:
                if payload.get("name") is not None:
                    template["name"] = payload.get("name")
                if payload.get("exercise_ids") is not None:
                    template["exercise_ids"] = payload.get("exercise_ids")
                template["updated_at"] = timestamp
                _set_projection("workout_templates", templates)
                break

    elif event_type == EventType.TEMPLATE_DELETED:
        # Remove template from workout_templates projection
        templates = _get_projection("workout_templates") or []
        template_id = payload.get("template_id")

        original_length = len(templates)
        templates = [t for t in templates if t["id"] != template_id]

        if len(templates) < original_length:
            _set_projection("workout_templates", templates)

    return derived if derived else None
