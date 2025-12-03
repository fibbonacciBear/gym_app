"""FastAPI application entry point."""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from backend.config import BASE_DIR
from backend.database import init_database
from backend.models import (
    EmitEventRequest,
    EmitEventResponse,
    HealthResponse,
    ProjectionResponse,
)
from backend.events import emit_event
from backend.database import get_projection, get_events

# Initialize FastAPI app
app = FastAPI(
    title="Voice Workout Tracker",
    description="A voice-first workout logging API",
    version="0.1.0"
)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_database("default")

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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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

# Serve frontend
FRONTEND_DIR = BASE_DIR / "frontend"

@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

# Mount static files
app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
