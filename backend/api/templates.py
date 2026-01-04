"""Template endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from uuid import uuid4

from backend.database import get_projection
from backend.events import emit_event, ConcurrencyConflictError
from backend.schema.events import EventType, SetType, WeightUnit
from backend.auth import get_current_user

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateExerciseResponse(BaseModel):
    """Exercise within a template."""
    exercise_id: str
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


class TemplateExerciseRequest(BaseModel):
    """Exercise spec for creating/updating templates."""
    exercise_id: str
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

    try:
        emit_event(EventType.TEMPLATE_CREATED, payload, user_id)
        templates = get_projection("workout_templates", user_id) or []
        created = next((t for t in templates if t["id"] == template_id), None)
        if not created:
            # Defensive guard: should not happen because emit_event is transactional
            raise HTTPException(status_code=500, detail="Template was created but not found")
        return created
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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
        payload["exercises"] = [ex.model_dump() for ex in request.exercises]
    elif request.exercise_ids is not None:
        payload["exercise_ids"] = request.exercise_ids

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

    try:
        result, derived = emit_event(
            EventType.WORKOUT_STARTED,
            {
                "name": template["name"],
                "from_template_id": template_id,
                "exercise_ids": template["exercise_ids"]
            },
            user_id
        )
        return {"success": True, "workout_id": result["payload"]["workout_id"]}
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
