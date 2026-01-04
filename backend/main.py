"""FastAPI application entry point."""
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import ValidationError
from datetime import datetime

from backend.config import BASE_DIR, AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_AUDIENCE
from backend.database import init_database, load_default_exercises, get_exercises
from backend.auth import get_current_user, get_current_user_email, get_current_user_optional
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

# Database initialization is now lazy - tables created on first access
# Run POST /api/admin/init-db once after deployment to load default exercises

# Health check
@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", version="0.1.0")

# Admin endpoint to initialize database (run once after deployment)
@app.post("/api/admin/init-db")
async def admin_init_db():
    """Initialize database schema and load default exercises. Run once per environment."""
    try:
        init_database("default")
        load_default_exercises("default")
        return {"status": "success", "message": "Database initialized with default exercises"}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

# Debug endpoint to check DB connection
@app.get("/api/debug/db-status")
async def debug_db_status():
    """Check database connection and table status."""
    from backend.config import USE_POSTGRES, get_database_url
    try:
        if USE_POSTGRES:
            import psycopg2
            conn = psycopg2.connect(get_database_url(), connect_timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM exercises WHERE user_id = 'default'")
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return {"status": "ok", "postgres": True, "exercise_count": count}
        else:
            return {"status": "ok", "postgres": False, "using": "sqlite"}
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()}

# Auth Configuration Endpoint (Public - GPT's suggestion)
@app.get("/api/auth/config")
async def get_auth_config():
    """
    Return Auth0 configuration for frontend.
    This avoids hardcoding credentials in JavaScript.
    
    Public endpoint - no authentication required.
    """
    return {
        "domain": AUTH0_DOMAIN,
        "clientId": AUTH0_CLIENT_ID,
        "audience": AUTH0_AUDIENCE
    }

# Debug endpoint to test auth
@app.get("/api/auth/debug")
async def debug_auth(user_id: str = Depends(get_current_user)):
    """Debug endpoint to verify authentication is working."""
    return {
        "authenticated": True,
        "user_id": user_id,
        "message": "Authentication successful!"
    }

# User Profile Endpoint (Protected)
@app.get("/api/user/profile")
async def get_user_profile(
    user_id: str = Depends(get_current_user),
    email: str = Depends(get_current_user_email)
):
    """Get current authenticated user profile."""
    return {
        "user_id": user_id,
        "email": email,
        "authenticated_at": datetime.utcnow().isoformat() + "Z"
    }

# Events API
@app.post("/api/events", response_model=EmitEventResponse)
async def emit_event_endpoint(
    request: EmitEventRequest,
    user_id: str = Depends(get_current_user)
):
    """Emit a new event. Requires authentication."""
    try:
        event_record, derived = emit_event(
            event_type=request.event_type,
            payload=request.payload,
            user_id=user_id  # Use authenticated user_id
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
async def list_events(
    event_type: str = None,
    limit: int = 100,
    user_id: str = Depends(get_current_user)
):
    """List events, optionally filtered by type. Requires authentication."""
    events = get_events(event_type=event_type, user_id=user_id, limit=limit)
    return {"events": events}

# Projections API
@app.get("/api/projections/{key}", response_model=ProjectionResponse)
async def get_projection_endpoint(
    key: str,
    user_id: str = Depends(get_current_user)
):
    """Get a projection by key. Requires authentication."""
    data = get_projection(key, user_id=user_id)
    return ProjectionResponse(key=key, data=data)

# Exercises API
@app.get("/api/exercises")
async def list_exercises(user_id: Optional[str] = Depends(get_current_user_optional)):
    """
    Get all available exercises.
    
    - If authenticated: returns shared (default) exercises + user's custom exercises
    - If not authenticated: returns only shared (default) exercises
    
    This allows the exercise library to work for both logged-in and logged-out users,
    while showing personalized content when available.
    """
    if user_id:
        # Authenticated: return shared + custom exercises
        exercises = get_exercises(user_id=user_id, include_shared=True)
    else:
        # Not authenticated: return only shared exercises
        exercises = get_exercises(user_id="default", include_shared=False)
    
    return {"exercises": exercises}

@app.get("/api/exercises/{exercise_id}/history")
async def get_exercise_history(
    exercise_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get history and PRs for a specific exercise. Requires authentication."""
    history = get_projection(f"exercise_history:{exercise_id}", user_id=user_id)
    records = get_projection(f"personal_records:{exercise_id}", user_id=user_id)

    # Get last session's sets for "previous values" display
    last_session = None
    if history and history.get("sessions"):
        last_session = history["sessions"][0]

    return {
        "exercise_id": exercise_id,
        "history": history,
        "personal_records": records,
        "last_session": last_session
    }

# Serve frontend
FRONTEND_DIR = BASE_DIR / "frontend"

@app.get("/")
async def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")

# Mount static files
app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")

# Serve favicon
@app.get("/favicon.svg")
async def favicon():
    """Serve the favicon."""
    favicon_path = FRONTEND_DIR / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")
