"""Voice processing endpoint."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.llm import process_voice_command
from backend.events import emit_event, ConcurrencyConflictError
from backend.schema.events import EventType
from backend.database import get_projection
from backend.auth import get_current_user

router = APIRouter(prefix="/api/voice", tags=["voice"])

class VoiceRequest(BaseModel):
    transcript: str
    mode: Optional[str] = None  # "plan_builder" or None (workout execution)

class VoiceResponse(BaseModel):
    success: bool
    action: Optional[str] = None
    event_result: Optional[Dict[str, Any]] = None
    message: str
    fallback: bool = False
    transcript: Optional[str] = None

@router.post("/process", response_model=VoiceResponse)
async def process_voice(
    request: VoiceRequest,
    user_id: str = Depends(get_current_user)
):
    """Process a voice command transcript. Requires authentication."""
    result = process_voice_command(request.transcript, user_id, mode=request.mode)

    if not result["success"]:
        return VoiceResponse(
            success=False,
            message=result.get("error", "Failed to process"),
            fallback=result.get("fallback", False),
            transcript=request.transcript
        )

    # If there's an action to perform
    if result.get("action") == "emit":
        args = result["arguments"]
        event_type_str = args["event_type"]
        payload = args["payload"]

        # In plan_builder mode, return action without executing
        # The frontend will handle adding to the template editor
        if request.mode == "plan_builder":
            return VoiceResponse(
                success=True,
                action="emit",
                event_result={
                    "event_type": event_type_str,
                    "payload": payload
                },
                message=result.get("message") or f"Add {payload.get('exercise_id', 'exercise')}"
            )

        try:
            event_type = EventType(event_type_str)

            # For SetLogged, auto-add exercise if not in workout (with proper event)
            if event_type == EventType.SET_LOGGED:
                current = get_projection("current_workout", user_id)
                if current:
                    exercise_id = payload.get("exercise_id")
                    exercise_exists = any(
                        ex["exercise_id"] == exercise_id
                        for ex in current.get("exercises", [])
                    )
                    if not exercise_exists:
                        # Emit ExerciseAdded event first
                        emit_event(
                            EventType.EXERCISE_ADDED,
                            {
                                "workout_id": current["id"],
                                "exercise_id": exercise_id
                            },
                            user_id
                        )

            event_record, derived = emit_event(event_type, payload, user_id)

            return VoiceResponse(
                success=True,
                action="emit",
                event_result={
                    "event_id": event_record["event_id"],
                    "event_type": event_type_str,
                    "derived": derived
                },
                message=generate_confirmation(event_type, payload, derived)
            )
        except ConcurrencyConflictError as e:
            return VoiceResponse(
                success=False,
                message=str(e),
                fallback=True,
                transcript=request.transcript
            )
        except ValueError as e:
            return VoiceResponse(
                success=False,
                message=f"Invalid command: {str(e)}",
                fallback=True,
                transcript=request.transcript
            )
        except Exception as e:
            return VoiceResponse(
                success=False,
                message=f"Failed to execute: {str(e)}",
                fallback=True,
                transcript=request.transcript
            )

    return VoiceResponse(
        success=True,
        message=result.get("message", "Command processed")
    )

def generate_confirmation(event_type: EventType, payload: dict, derived: dict) -> str:
    """Generate a human-readable confirmation message."""
    if event_type == EventType.SET_LOGGED:
        weight = payload.get("weight")
        reps = payload.get("reps")
        unit = payload.get("unit", "kg")
        exercise = payload.get("exercise_id", "").replace("-", " ").title()
        msg = f"Logged {weight}{unit} × {reps}"
        if exercise:
            msg += f" for {exercise}"
        if derived and derived.get("is_pr"):
            msg += " 🏆 New PR!"
        return msg
    elif event_type == EventType.WORKOUT_STARTED:
        return "Workout started!"
    elif event_type == EventType.WORKOUT_COMPLETED:
        return "Workout saved!"
    elif event_type == EventType.EXERCISE_ADDED:
        exercise = payload.get("exercise_id", "").replace("-", " ").title()
        return f"Added {exercise}"
    return "Done!"
