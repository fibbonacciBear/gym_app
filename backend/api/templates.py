"""Template endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from uuid import uuid4

from backend.database import get_projection
from backend.events import emit_event, ConcurrencyConflictError
from backend.schema.events import EventType

router = APIRouter(prefix="/api/templates", tags=["templates"])

class TemplateResponse(BaseModel):
    id: str
    name: str
    exercise_ids: List[str]
    created_at: str
    last_used_at: Optional[str]
    use_count: int

class CreateTemplateRequest(BaseModel):
    name: str
    exercise_ids: List[str]

class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    exercise_ids: Optional[List[str]] = None

@router.get("", response_model=List[TemplateResponse])
async def list_templates():
    """List all templates."""
    templates = get_projection("workout_templates", "default") or []
    return templates

@router.post("", response_model=TemplateResponse)
async def create_template(request: CreateTemplateRequest):
    """Create a new template."""
    template_id = str(uuid4())
    try:
        emit_event(
            EventType.TEMPLATE_CREATED,
            {
                "template_id": template_id,
                "name": request.name,
                "exercise_ids": request.exercise_ids
            },
            "default"
        )
        templates = get_projection("workout_templates", "default") or []
        return next(t for t in templates if t["id"] == template_id)
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """Get a template by ID."""
    templates = get_projection("workout_templates", "default") or []
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """Delete a template."""
    try:
        emit_event(
            EventType.TEMPLATE_DELETED,
            {"template_id": template_id},
            "default"
        )
        return {"success": True}
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{template_id}/start")
async def start_from_template(template_id: str):
    """Start a new workout from a template."""
    templates = get_projection("workout_templates", "default") or []
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
            "default"
        )
        return {"success": True, "workout_id": result["payload"]["workout_id"]}
    except ConcurrencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
