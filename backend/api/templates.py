"""Template endpoints."""
import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from uuid import uuid4

logger = logging.getLogger(__name__)

from backend.database import get_projection
from backend.events import emit_event, ConcurrencyConflictError
from backend.schema.events import EventType, SetType, WeightUnit
from backend.auth import get_current_user

router = APIRouter(prefix="/api/templates", tags=["templates"])


class SetGroupResponse(BaseModel):
    """A group of sets with the same targets."""
    target_sets: int
    target_reps: Optional[int] = None
    target_weight: Optional[float] = None
    target_unit: str = "kg"
    set_type: str = "working"  # warmup, working, dropset, pyramid, other
    rest_seconds: int = 60
    notes: Optional[str] = None


class TemplateExerciseResponse(BaseModel):
    """Exercise within a template."""
    exercise_id: str
    # NEW: set groups (takes precedence if present)
    set_groups: Optional[List[SetGroupResponse]] = None
    # OLD: single-target fields (for backward compatibility)
    target_sets: Optional[int] = None
    target_reps: Optional[int] = None
    target_weight: Optional[float] = None
    target_unit: str = "kg"
    set_type: str = "standard"
    rest_seconds: int = 60
    notes: Optional[str] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    exercise_ids: List[str]  # Legacy field for backwards compat
    exercises: Optional[List[TemplateExerciseResponse]] = None  # New enhanced format
    created_at: str
    last_used_at: Optional[str] = None
    use_count: int = 0


class SetGroupRequest(BaseModel):
    """A group of sets with the same targets."""
    target_sets: int = Field(ge=1)
    target_reps: Optional[int] = Field(default=None, ge=1)
    target_weight: Optional[float] = Field(default=None, ge=0)
    target_unit: str = "kg"
    set_type: str = "working"  # warmup, working, dropset, pyramid, other
    rest_seconds: int = Field(default=60, ge=0)
    notes: Optional[str] = None


class TemplateExerciseRequest(BaseModel):
    """Exercise spec for creating/updating templates."""
    exercise_id: str
    # NEW: set groups (takes precedence if present)
    set_groups: Optional[List[SetGroupRequest]] = None
    # OLD: single-target fields (for backward compatibility)
    target_sets: Optional[int] = Field(default=None, ge=1)
    target_reps: Optional[int] = Field(default=None, ge=1)
    target_weight: Optional[float] = Field(default=None, ge=0)
    target_unit: str = "kg"
    set_type: str = "standard"
    rest_seconds: int = Field(default=60, ge=0)
    notes: Optional[str] = None


class CreateTemplateRequest(BaseModel):
    name: str
    # Support both legacy and new format
    exercise_ids: Optional[List[str]] = None  # Legacy: just IDs
    exercises: Optional[List[TemplateExerciseRequest]] = None  # New: full specs


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    exercise_ids: Optional[List[str]] = None  # Legacy
    exercises: Optional[List[TemplateExerciseRequest]] = None  # New

@router.get("", response_model=List[TemplateResponse])
async def list_templates(user_id: str = Depends(get_current_user)):
    """List all templates. Requires authentication."""
    templates = get_projection("workout_templates", user_id) or []
    return templates

@router.post("", response_model=TemplateResponse)
async def create_template(
    request: CreateTemplateRequest,
    user_id: str = Depends(get_current_user)
):
    """Create a new template. Requires authentication."""
    logger.debug(f"Creating template: name={request.name}, user_id={user_id}")
    logger.debug(f"Request data: exercises={request.exercises}, exercise_ids={request.exercise_ids}")

    # Check for duplicate name
    templates = get_projection("workout_templates", user_id) or []
    name_lower = request.name.strip().lower()
    if any(t["name"].strip().lower() == name_lower for t in templates):
        raise HTTPException(status_code=400, detail="A template with this name already exists")

    template_id = str(uuid4())

    # Build payload based on request format
    payload = {
        "template_id": template_id,
        "name": request.name,
    }

    if request.exercises:
        # New format: full exercise specs
        payload["exercises"] = [ex.model_dump() for ex in request.exercises]
    elif request.exercise_ids:
        # Legacy format: just IDs
        payload["exercise_ids"] = request.exercise_ids
    else:
        # Empty template
        payload["exercises"] = []

    logger.debug(f"Payload for emit_event: {payload}")

    try:
        emit_event(EventType.TEMPLATE_CREATED, payload, user_id)
        logger.debug("emit_event succeeded")
        templates = get_projection("workout_templates", user_id) or []
        created = next((t for t in templates if t["id"] == template_id), None)
        if not created:
            # Defensive guard: should not happen because emit_event is transactional
            logger.error(f"Template {template_id} was created but not found in projection")
            raise HTTPException(status_code=500, detail="Template was created but not found")
        logger.debug(f"Template created successfully: {created}")
        return created
    except ConcurrencyConflictError as e:
        logger.error(f"Concurrency conflict: {e}")
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error creating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get a template by ID. Requires authentication."""
    templates = get_projection("workout_templates", user_id) or []
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    user_id: str = Depends(get_current_user)
):
    """Update an existing template. Requires authentication."""
    logger.debug(f"[UPDATE_TEMPLATE] Received request for template {template_id}")
    logger.debug(f"[UPDATE_TEMPLATE] request.exercises: {request.exercises}")

    # Check for duplicate name (excluding current template)
    if request.name is not None:
        templates = get_projection("workout_templates", user_id) or []
        name_lower = request.name.strip().lower()
        if any(t["name"].strip().lower() == name_lower and t["id"] != template_id for t in templates):
            raise HTTPException(status_code=400, detail="A template with this name already exists")

    # Build payload
    payload = {"template_id": template_id}

    if request.name is not None:
        payload["name"] = request.name
    if request.exercises is not None:
        exercises_dump = [ex.model_dump() for ex in request.exercises]
        logger.debug(f"[UPDATE_TEMPLATE] exercises after model_dump: {exercises_dump}")
        for ex in exercises_dump:
            logger.debug(f"[UPDATE_TEMPLATE] Exercise {ex.get('exercise_id')} set_groups: {ex.get('set_groups')}")
        payload["exercises"] = exercises_dump
    elif request.exercise_ids is not None:
        payload["exercise_ids"] = request.exercise_ids

    logger.debug(f"[UPDATE_TEMPLATE] Final payload: {payload}")

    try:
        emit_event(EventType.TEMPLATE_UPDATED, payload, user_id)
        templates = get_projection("workout_templates", user_id) or []
        updated = next((t for t in templates if t["id"] == template_id), None)
        if not updated:
            raise HTTPException(status_code=404, detail="Template not found")
        return updated
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a template. Requires authentication."""
    try:
        emit_event(
            EventType.TEMPLATE_DELETED,
            {"template_id": template_id},
            user_id
        )
        return {"success": True}
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{template_id}/start")
async def start_from_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """Start a new workout from a template. Requires authentication."""
    templates = get_projection("workout_templates", user_id) or []
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Extract full exercise details from template (if using new format with targets)
    exercise_plans = []
    if template.get("exercises"):
        # New format: full exercise specs with targets
        exercise_plans = template["exercises"]
    else:
        # Legacy format: just IDs (no targets)
        exercise_plans = [{"exercise_id": ex_id} for ex_id in template.get("exercise_ids", [])]

    try:
        result, derived = emit_event(
            EventType.WORKOUT_STARTED,
            {
                "name": template["name"],
                "from_template_id": template_id,
                "exercise_ids": [ex.get("exercise_id") for ex in exercise_plans],
                "exercise_plans": exercise_plans  # Pass full plan details for guided mode
            },
            user_id
        )
        return {"success": True, "workout_id": result["payload"]["workout_id"]}
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error starting workout from template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
