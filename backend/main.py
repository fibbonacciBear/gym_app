"""FastAPI application entry point."""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import ValidationError

from backend.config import BASE_DIR
from backend.database import init_database, load_default_exercises, get_exercises
from backend.models import (
    EmitEventRequest,
    EmitEventResponse,
    HealthResponse,
    ProjectionResponse,
)
from backend.events import emit_event, ConcurrencyConflictError
from backend.database import get_projection, get_events
from backend.api.history import router as history_router
from backend.api.templates import router as templates_router
from backend.api.voice import router as voice_router

# Initialize FastAPI app
app = FastAPI(
    title="Voice Workout Tracker",
    description="A voice-first workout logging API",
    version="0.1.0"
)

# Include routers
app.include_router(history_router)
app.include_router(templates_router)
app.include_router(voice_router)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_database("default")
    load_default_exercises("default")

# Health check
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", version="0.1.0")

# Events API
@app.post("/api/events", response_model=EmitEventResponse)
async def emit_event_endpoint(request: EmitEventRequest):
    """Emit a new event."""
    try:
        event_record, derived = emit_event(
            event_type=request.event_type,
            payload=request.payload,
            user_id="default"
        )
        return EmitEventResponse(
            success=True,
            event_id=event_record["event_id"],
            timestamp=event_record["timestamp"],
            event_type=request.event_type,
            payload=event_record["payload"],
            derived=derived
        )
    except ConcurrencyConflictError as e:
        # Database lock conflict - return 409 Conflict so client can retry
        raise HTTPException(status_code=409, detail=str(e))
    except ValidationError as e:
        # Pydantic validation error - return 422 Unprocessable Entity
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        # Business logic validation error - return 400 Bad Request
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected error - return 500 Internal Server Error
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/events")
async def list_events(event_type: str = None, limit: int = 100):
    """List events, optionally filtered by type."""
    events = get_events(event_type=event_type, user_id="default", limit=limit)
    return {"events": events}

# Projections API
@app.get("/api/projections/{key}", response_model=ProjectionResponse)
async def get_projection_endpoint(key: str):
    """Get a projection by key."""
    data = get_projection(key, user_id="default")
    return ProjectionResponse(key=key, data=data)

# Exercises API
@app.get("/api/exercises")
async def list_exercises():
    """Get all available exercises."""
    exercises = get_exercises(user_id="default")
    return {"exercises": exercises}

# Serve frontend
FRONTEND_DIR = BASE_DIR / "frontend"

@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

# Mount static files
app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
