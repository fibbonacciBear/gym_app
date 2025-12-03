# Voice-First Workout Tracker – Implementation Plan

## Overview

This document provides a detailed, sprint-by-sprint implementation plan for building the voice-first workout tracker MVP. Each sprint delivers customer-facing value and builds on previous sprints.

**Target Executor:** Claude Code (Claude 4.5 Sonnet)
**Total Sprints:** 8
**Estimated Duration:** 11 days

---

## Project Structure

Create this directory structure before starting:

```
/gym_app/
├── app_specification.md          # Product spec (exists)
├── technical_specification.md    # Tech spec (exists)
├── implementation_plan.md        # This document
├── requirements.txt              # Python dependencies
├── backend/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Configuration
│   ├── database.py               # SQLite operations
│   ├── models.py                 # Pydantic models
│   ├── events.py                 # Event handling logic
│   ├── projections.py            # Projection calculations
│   ├── aggregates.py             # Aggregate calculations
│   ├── llm.py                    # LLM integration
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── events.py             # Event type definitions
│   │   └── validation.py         # Schema validation
│   └── api/
│       ├── __init__.py
│       ├── events.py             # Event endpoints
│       ├── projections.py        # Projection endpoints
│       ├── templates.py          # Template endpoints
│       ├── exercises.py          # Exercise endpoints
│       ├── stats.py              # Stats endpoints
│       └── voice.py              # Voice processing endpoint
├── frontend/
│   ├── index.html                # Main HTML file
│   ├── css/
│   │   └── styles.css            # Tailwind + custom styles
│   └── js/
│       ├── app.js                # Main Alpine.js app
│       ├── voice.js              # Web Speech API integration
│       ├── api.js                # API client
│       └── tutorial.js           # Tutorial logic
├── data/
│   └── exercises.json            # Default exercise library
├── tests/
│   ├── __init__.py
│   ├── test_events.py
│   ├── test_projections.py
│   └── test_api.py
└── workspace/
    └── default/                  # Default user workspace
        └── .gitkeep
```

---

## Dependencies

Create `requirements.txt`:

```
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
python-dotenv==1.0.0
openai==1.12.0
httpx==0.26.0
pytest==7.4.4
pytest-asyncio==0.23.3
```

---

## Sprint 1: Walking Skeleton

### Goal
Create the thinnest possible end-to-end slice that proves the architecture works: user can start and finish a workout, events are stored in SQLite.

### Duration: 1 day

### Dependencies: None (foundation sprint)

### Deliverables

#### 1.1 Configuration (`backend/config.py`)

```python
"""Application configuration."""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
DEFAULT_USER_ID = "default"

# Database
def get_db_path(user_id: str = DEFAULT_USER_ID) -> Path:
    """Get database path for a user."""
    user_dir = WORKSPACE_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "gym.db"

# LLM (for later sprints)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = "gpt-4o-mini"
LLM_MAX_TOKENS = 200
```

#### 1.2 Database Setup (`backend/database.py`)

```python
"""SQLite database operations."""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from backend.config import get_db_path

def init_database(user_id: str = "default") -> None:
    """Initialize database with required tables."""
    db_path = get_db_path(user_id)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Events table (append-only event log)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                schema_version INTEGER DEFAULT 1
            )
        """)
        
        # Indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type 
            ON events(event_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp 
            ON events(timestamp)
        """)
        
        # Projections table (derived state)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projections (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Aggregates table (time-based stats)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aggregates (
                period_type TEXT NOT NULL,
                period_key TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (period_type, period_key)
            )
        """)
        
        # Exercises table (library)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exercises (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                description TEXT,
                is_custom INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        
        conn.commit()

@contextmanager
def get_connection(user_id: str = "default"):
    """Get database connection context manager."""
    db_path = get_db_path(user_id)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def append_event(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    user_id: str = "default"
) -> Dict[str, Any]:
    """Append an event to the event store."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO events (event_id, timestamp, event_type, payload)
            VALUES (?, ?, ?, ?)
            """,
            (event_id, timestamp, event_type, json.dumps(payload))
        )
        conn.commit()
        
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "payload": payload
    }

def get_events(
    event_type: Optional[str] = None,
    user_id: str = "default",
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get events from the store, optionally filtered by type."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        
        if event_type:
            cursor.execute(
                """
                SELECT event_id, timestamp, event_type, payload
                FROM events
                WHERE event_type = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (event_type, limit)
            )
        else:
            cursor.execute(
                """
                SELECT event_id, timestamp, event_type, payload
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            )
        
        rows = cursor.fetchall()
        return [
            {
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"])
            }
            for row in rows
        ]

def get_projection(key: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
    """Get a projection by key."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT data FROM projections WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["data"])
        return None

def set_projection(key: str, data: Dict[str, Any], user_id: str = "default") -> None:
    """Set a projection value."""
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO projections (key, data, updated_at)
            VALUES (?, ?, ?)
            """,
            (key, json.dumps(data), timestamp)
        )
        conn.commit()
```

#### 1.3 Event Models (`backend/schema/events.py`)

```python
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

# Payload models for each event type
class WorkoutStartedPayload(BaseModel):
    workout_id: str = Field(default_factory=lambda: str(uuid4()))
    name: Optional[str] = None
    from_template_id: Optional[str] = None
    exercise_ids: Optional[List[str]] = None

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
    weight: float = Field(ge=0)
    reps: int = Field(ge=0)
    unit: WeightUnit = WeightUnit.KG

class SetModifiedPayload(BaseModel):
    original_event_id: str
    weight: Optional[float] = Field(default=None, ge=0)
    reps: Optional[int] = Field(default=None, ge=0)
    unit: Optional[WeightUnit] = None

class SetDeletedPayload(BaseModel):
    original_event_id: str
    reason: Optional[str] = None

class TemplateCreatedPayload(BaseModel):
    template_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    exercise_ids: List[str]
    source_workout_id: Optional[str] = None

class TemplateUpdatedPayload(BaseModel):
    template_id: str
    name: Optional[str] = None
    exercise_ids: Optional[List[str]] = None

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
```

#### 1.4 Pydantic Models (`backend/models.py`)

```python
"""API request/response models."""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from backend.schema.events import EventType, WeightUnit

class EmitEventRequest(BaseModel):
    """Request to emit an event."""
    event_type: EventType
    payload: Dict[str, Any]

class EmitEventResponse(BaseModel):
    """Response after emitting an event."""
    success: bool
    event_id: str
    timestamp: str
    event_type: EventType
    payload: Dict[str, Any]
    derived: Optional[Dict[str, Any]] = None  # e.g., is_pr, total_volume

class EventRecord(BaseModel):
    """An event record from the store."""
    event_id: str
    timestamp: str
    event_type: str
    payload: Dict[str, Any]

class ProjectionResponse(BaseModel):
    """A projection value."""
    key: str
    data: Optional[Dict[str, Any]]
    
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
```

#### 1.5 Event Handler (`backend/events.py`)

```python
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
        # Create current_workout projection
        workout_id = payload.get("workout_id")
        current_workout = {
            "id": workout_id,
            "started_at": None,  # Will be set from event timestamp
            "from_template_id": payload.get("from_template_id"),
            "focus_exercise": None,
            "exercises": []
        }
        
        # If starting from template with exercises, add them
        exercise_ids = payload.get("exercise_ids", [])
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
            # Add to workout history
            history = get_projection("workout_history", user_id) or []
            current["completed_at"] = payload.get("notes", "")
            history.insert(0, current)  # Most recent first
            set_projection("workout_history", history, user_id)
            
        # Clear current workout
        set_projection("current_workout", None, user_id)
        
    elif event_type == EventType.WORKOUT_DISCARDED:
        # Just clear current workout
        set_projection("current_workout", None, user_id)
        
    return derived if derived else None
```

#### 1.6 FastAPI App (`backend/main.py`)

```python
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
```

#### 1.7 Frontend HTML (`frontend/index.html`)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Workout Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <link rel="stylesheet" href="/css/styles.css">
</head>
<body class="bg-gray-900 text-white min-h-screen">
    <div x-data="workoutApp()" class="container mx-auto px-4 py-8 max-w-md">
        
        <!-- Header -->
        <header class="text-center mb-8">
            <h1 class="text-2xl font-bold">🏋️ Workout Tracker</h1>
            <p class="text-gray-400 text-sm">Voice-first logging</p>
        </header>
        
        <!-- No Active Workout -->
        <div x-show="!currentWorkout" class="text-center">
            <p class="text-gray-400 mb-6">No workout in progress</p>
            <button 
                @click="startWorkout()"
                class="bg-green-600 hover:bg-green-700 text-white font-bold py-4 px-8 rounded-xl text-xl transition-colors"
            >
                Start Workout
            </button>
        </div>
        
        <!-- Active Workout -->
        <div x-show="currentWorkout" class="space-y-6">
            
            <!-- Workout Header -->
            <div class="bg-gray-800 rounded-xl p-4">
                <div class="flex justify-between items-center">
                    <div>
                        <h2 class="text-lg font-semibold">Current Workout</h2>
                        <p class="text-gray-400 text-sm" x-text="currentWorkout?.id?.slice(0, 8)"></p>
                    </div>
                    <span class="bg-green-600 px-3 py-1 rounded-full text-sm">Active</span>
                </div>
            </div>
            
            <!-- Exercise List (placeholder for Sprint 2) -->
            <div class="bg-gray-800 rounded-xl p-4">
                <p class="text-gray-400 text-center">Exercises will appear here</p>
            </div>
            
            <!-- Action Buttons -->
            <div class="grid grid-cols-2 gap-4">
                <button 
                    @click="discardWorkout()"
                    class="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-xl transition-colors"
                >
                    Discard
                </button>
                <button 
                    @click="finishWorkout()"
                    class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-6 rounded-xl transition-colors"
                >
                    Finish
                </button>
            </div>
            
        </div>
        
        <!-- Status Message -->
        <div 
            x-show="statusMessage" 
            x-transition
            class="fixed bottom-4 left-4 right-4 bg-gray-800 rounded-xl p-4 text-center"
            :class="{'border-green-500 border': statusType === 'success', 'border-red-500 border': statusType === 'error'}"
        >
            <p x-text="statusMessage"></p>
        </div>
        
    </div>
    
    <script src="/js/api.js"></script>
    <script src="/js/app.js"></script>
</body>
</html>
```

#### 1.8 API Client (`frontend/js/api.js`)

```javascript
/**
 * API client for the workout tracker backend.
 */
const API = {
    baseUrl: '',
    
    /**
     * Emit an event to the backend.
     */
    async emitEvent(eventType, payload) {
        const response = await fetch(`${this.baseUrl}/api/events`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_type: eventType,
                payload: payload
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to emit event');
        }
        
        return response.json();
    },
    
    /**
     * Get a projection.
     */
    async getProjection(key) {
        const response = await fetch(`${this.baseUrl}/api/projections/${key}`);
        
        if (!response.ok) {
            throw new Error('Failed to get projection');
        }
        
        const result = await response.json();
        return result.data;
    },
    
    /**
     * List events.
     */
    async listEvents(eventType = null, limit = 100) {
        let url = `${this.baseUrl}/api/events?limit=${limit}`;
        if (eventType) {
            url += `&event_type=${eventType}`;
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error('Failed to list events');
        }
        
        const result = await response.json();
        return result.events;
    }
};
```

#### 1.9 Main App (`frontend/js/app.js`)

```javascript
/**
 * Main workout app using Alpine.js
 */
function workoutApp() {
    return {
        // State
        currentWorkout: null,
        statusMessage: '',
        statusType: 'success',
        
        // Initialize
        async init() {
            await this.loadCurrentWorkout();
        },
        
        // Load current workout from projection
        async loadCurrentWorkout() {
            try {
                this.currentWorkout = await API.getProjection('current_workout');
            } catch (error) {
                console.error('Failed to load current workout:', error);
            }
        },
        
        // Start a new workout
        async startWorkout() {
            try {
                const result = await API.emitEvent('WorkoutStarted', {});
                this.showStatus('Workout started!', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to start workout: ' + error.message, 'error');
            }
        },
        
        // Finish the current workout
        async finishWorkout() {
            if (!this.currentWorkout) return;
            
            try {
                await API.emitEvent('WorkoutCompleted', {
                    workout_id: this.currentWorkout.id
                });
                this.showStatus('Workout saved!', 'success');
                this.currentWorkout = null;
            } catch (error) {
                this.showStatus('Failed to finish workout: ' + error.message, 'error');
            }
        },
        
        // Discard the current workout
        async discardWorkout() {
            if (!this.currentWorkout) return;
            
            if (!confirm('Discard this workout? All data will be lost.')) {
                return;
            }
            
            try {
                await API.emitEvent('WorkoutDiscarded', {
                    workout_id: this.currentWorkout.id
                });
                this.showStatus('Workout discarded', 'success');
                this.currentWorkout = null;
            } catch (error) {
                this.showStatus('Failed to discard workout: ' + error.message, 'error');
            }
        },
        
        // Show status message
        showStatus(message, type = 'success') {
            this.statusMessage = message;
            this.statusType = type;
            setTimeout(() => {
                this.statusMessage = '';
            }, 3000);
        }
    };
}
```

#### 1.10 CSS Styles (`frontend/css/styles.css`)

```css
/* Custom styles for workout tracker */

/* Ensure dark mode */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Large touch targets */
button {
    min-height: 48px;
    touch-action: manipulation;
}

/* Transitions */
.transition-colors {
    transition: background-color 0.15s ease;
}

/* Status bar animation */
[x-transition] {
    transition: opacity 0.2s ease, transform 0.2s ease;
}
```

### Sprint 1: Test Criteria

Run these tests to verify Sprint 1 is complete:

```bash
# 1. Start the server
cd /path/to/gym_app
uvicorn backend.main:app --reload --port 8000

# 2. Test health endpoint
curl http://localhost:8000/api/health
# Expected: {"status":"healthy","version":"0.1.0"}

# 3. Open browser to http://localhost:8000
# Expected: See "No workout in progress" with Start button

# 4. Click "Start Workout"
# Expected: See "Current Workout" with Active badge

# 5. Click "Finish"
# Expected: See "Workout saved!" message, return to start screen

# 6. Verify events stored
curl http://localhost:8000/api/events
# Expected: See WorkoutStarted and WorkoutCompleted events
```

### Sprint 1: Definition of Done

- [ ] Server starts without errors
- [ ] Health endpoint returns 200
- [ ] Can start a workout via UI
- [ ] Can finish a workout via UI
- [ ] Can discard a workout via UI
- [ ] Events are stored in SQLite
- [ ] Events are retrievable via API
- [ ] current_workout projection updates correctly

---

## Sprint 2: Full Workout Logging (Manual)

### Goal
Complete manual workout logging: add exercises, log sets, view/delete sets.

### Duration: 2 days

### Dependencies: Sprint 1 complete

### Deliverables

#### 2.1 Exercise Library (`data/exercises.json`)

```json
{
  "exercises": [
    {"id": "bench-press", "name": "Bench Press", "category": "chest"},
    {"id": "incline-bench-press", "name": "Incline Bench Press", "category": "chest"},
    {"id": "dumbbell-fly", "name": "Dumbbell Fly", "category": "chest"},
    {"id": "deadlift", "name": "Deadlift", "category": "back"},
    {"id": "barbell-row", "name": "Barbell Row", "category": "back"},
    {"id": "pull-up", "name": "Pull-up", "category": "back"},
    {"id": "lat-pulldown", "name": "Lat Pulldown", "category": "back"},
    {"id": "overhead-press", "name": "Overhead Press", "category": "shoulders"},
    {"id": "lateral-raise", "name": "Lateral Raise", "category": "shoulders"},
    {"id": "face-pull", "name": "Face Pull", "category": "shoulders"},
    {"id": "barbell-curl", "name": "Barbell Curl", "category": "arms"},
    {"id": "tricep-pushdown", "name": "Tricep Pushdown", "category": "arms"},
    {"id": "hammer-curl", "name": "Hammer Curl", "category": "arms"},
    {"id": "squat", "name": "Squat", "category": "legs"},
    {"id": "leg-press", "name": "Leg Press", "category": "legs"},
    {"id": "romanian-deadlift", "name": "Romanian Deadlift", "category": "legs"},
    {"id": "leg-curl", "name": "Leg Curl", "category": "legs"},
    {"id": "leg-extension", "name": "Leg Extension", "category": "legs"},
    {"id": "calf-raise", "name": "Calf Raise", "category": "legs"},
    {"id": "plank", "name": "Plank", "category": "core"}
  ]
}
```

#### 2.2 Load Exercises on Startup

Update `backend/database.py` - add function:

```python
import json
from backend.config import BASE_DIR

def load_default_exercises(user_id: str = "default") -> None:
    """Load default exercises into database."""
    exercises_file = BASE_DIR / "data" / "exercises.json"
    
    if not exercises_file.exists():
        return
        
    with open(exercises_file) as f:
        data = json.load(f)
    
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        for ex in data["exercises"]:
            cursor.execute(
                """
                INSERT OR IGNORE INTO exercises (id, name, category, is_custom)
                VALUES (?, ?, ?, 0)
                """,
                (ex["id"], ex["name"], ex.get("category"))
            )
        conn.commit()

def get_exercises(user_id: str = "default") -> List[Dict[str, Any]]:
    """Get all exercises."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, is_custom FROM exercises ORDER BY name")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_exercise(exercise_id: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
    """Get a single exercise by ID."""
    with get_connection(user_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, category, is_custom FROM exercises WHERE id = ?",
            (exercise_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
```

Update `backend/main.py` startup:

```python
@app.on_event("startup")
async def startup():
    init_database("default")
    load_default_exercises("default")  # Add this line
```

#### 2.3 Update Event Handler for Sets

Update `backend/events.py` - extend `update_projections`:

```python
def update_projections(
    event_type: EventType,
    payload: Dict[str, Any],
    user_id: str
) -> Optional[Dict[str, Any]]:
    """Update projections based on event. Returns derived data."""
    derived = {}
    
    if event_type == EventType.WORKOUT_STARTED:
        # ... existing code ...
        pass
        
    elif event_type == EventType.EXERCISE_ADDED:
        current = get_projection("current_workout", user_id)
        if current:
            exercise_id = payload["exercise_id"]
            # Check if exercise already exists
            existing = next(
                (e for e in current["exercises"] if e["exercise_id"] == exercise_id),
                None
            )
            if not existing:
                current["exercises"].append({
                    "exercise_id": exercise_id,
                    "sets": []
                })
            current["focus_exercise"] = exercise_id
            set_projection("current_workout", current, user_id)
            
    elif event_type == EventType.SET_LOGGED:
        current = get_projection("current_workout", user_id)
        if current:
            exercise_id = payload["exercise_id"]
            
            # Find or create exercise entry
            exercise_entry = next(
                (e for e in current["exercises"] if e["exercise_id"] == exercise_id),
                None
            )
            if not exercise_entry:
                exercise_entry = {"exercise_id": exercise_id, "sets": []}
                current["exercises"].append(exercise_entry)
            
            # Add the set
            set_data = {
                "weight": payload["weight"],
                "reps": payload["reps"],
                "unit": payload["unit"],
                "logged_at": datetime.utcnow().isoformat() + "Z"
            }
            exercise_entry["sets"].append(set_data)
            
            # Update focus
            current["focus_exercise"] = exercise_id
            
            set_projection("current_workout", current, user_id)
            
            # TODO: Check for PR in Sprint 6
            derived["set_index"] = len(exercise_entry["sets"]) - 1
            
    elif event_type == EventType.SET_DELETED:
        # Find and remove the set by event ID
        # This requires tracking event IDs in sets - simplified for now
        pass
        
    elif event_type == EventType.WORKOUT_COMPLETED:
        # ... existing code ...
        pass
        
    elif event_type == EventType.WORKOUT_DISCARDED:
        # ... existing code ...
        pass
        
    return derived if derived else None
```

#### 2.4 Exercises API (`backend/api/exercises.py`)

```python
"""Exercise endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel

from backend.database import get_exercises, get_exercise

router = APIRouter(prefix="/api/exercises", tags=["exercises"])

class ExerciseResponse(BaseModel):
    id: str
    name: str
    category: str | None
    is_custom: bool

@router.get("", response_model=List[ExerciseResponse])
async def list_exercises():
    """List all exercises."""
    exercises = get_exercises("default")
    return exercises

@router.get("/{exercise_id}", response_model=ExerciseResponse)
async def get_exercise_endpoint(exercise_id: str):
    """Get a single exercise."""
    exercise = get_exercise(exercise_id, "default")
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise
```

Register in `backend/main.py`:

```python
from backend.api.exercises import router as exercises_router
app.include_router(exercises_router)
```

#### 2.5 Updated Frontend HTML

See continuation in next section...

### Sprint 2: Test Criteria

```bash
# 1. Start server and open http://localhost:8000

# 2. Start a workout

# 3. Click "+ Add Exercise" 
# Expected: See exercise list modal

# 4. Select "Bench Press"
# Expected: Bench Press appears in workout, focused

# 5. Enter weight: 100, reps: 8, click "Add Set"
# Expected: Set appears under Bench Press

# 6. Add 2 more sets
# Expected: 3 sets visible

# 7. Click "Finish"
# Expected: Workout saved

# 8. Verify via API
curl http://localhost:8000/api/events
# Expected: See ExerciseAdded and SetLogged events
```

---

## Sprint 3: Workout History

### Goal
Users can view their past workouts.

### Duration: 1 day

### Dependencies: Sprint 2 complete (need completed workouts to view)

### Deliverables

#### 3.1 History Projection Updates

Update `backend/events.py` - improve WorkoutCompleted handler:

```python
elif event_type == EventType.WORKOUT_COMPLETED:
    current = get_projection("current_workout", user_id)
    if current:
        # Calculate workout stats
        total_sets = sum(len(e["sets"]) for e in current["exercises"])
        total_volume = sum(
            s["weight"] * s["reps"]
            for e in current["exercises"]
            for s in e["sets"]
        )
        
        # Create history entry
        history_entry = {
            "id": current["id"],
            "started_at": current.get("started_at"),
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "from_template_id": current.get("from_template_id"),
            "exercises": current["exercises"],
            "notes": payload.get("notes", ""),
            "stats": {
                "exercise_count": len(current["exercises"]),
                "total_sets": total_sets,
                "total_volume": total_volume
            }
        }
        
        # Add to history
        history = get_projection("workout_history", user_id) or []
        history.insert(0, history_entry)
        set_projection("workout_history", history, user_id)
        
    # Clear current workout
    set_projection("current_workout", None, user_id)
    
    derived["total_sets"] = total_sets if current else 0
    derived["total_volume"] = total_volume if current else 0
```

#### 3.2 History API Endpoints

Create `backend/api/history.py`:

```python
"""Workout history endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.database import get_projection

router = APIRouter(prefix="/api/history", tags=["history"])

class WorkoutStats(BaseModel):
    exercise_count: int
    total_sets: int
    total_volume: float

class SetRecord(BaseModel):
    weight: float
    reps: int
    unit: str
    logged_at: str

class ExerciseRecord(BaseModel):
    exercise_id: str
    sets: List[SetRecord]

class WorkoutHistoryEntry(BaseModel):
    id: str
    started_at: Optional[str]
    completed_at: str
    exercises: List[ExerciseRecord]
    stats: WorkoutStats
    notes: Optional[str] = ""

@router.get("", response_model=List[WorkoutHistoryEntry])
async def list_workout_history(limit: int = 50):
    """Get workout history, most recent first."""
    history = get_projection("workout_history", "default") or []
    return history[:limit]

@router.get("/{workout_id}", response_model=WorkoutHistoryEntry)
async def get_workout_detail(workout_id: str):
    """Get a specific workout from history."""
    history = get_projection("workout_history", "default") or []
    workout = next((w for w in history if w["id"] == workout_id), None)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return workout
```

Register in `backend/main.py`:

```python
from backend.api.history import router as history_router
app.include_router(history_router)
```

#### 3.3 Frontend: History Tab

Add to `frontend/index.html` - navigation tabs and history view:

```html
<!-- Add tab navigation after header -->
<nav class="flex mb-6 bg-gray-800 rounded-xl p-1">
    <button 
        @click="activeTab = 'workout'"
        :class="{'bg-gray-700': activeTab === 'workout'}"
        class="flex-1 py-2 rounded-lg transition-colors"
    >
        Workout
    </button>
    <button 
        @click="activeTab = 'history'; loadHistory()"
        :class="{'bg-gray-700': activeTab === 'history'}"
        class="flex-1 py-2 rounded-lg transition-colors"
    >
        History
    </button>
</nav>

<!-- History Tab Content -->
<div x-show="activeTab === 'history'" class="space-y-4">
    <template x-if="historyLoading">
        <p class="text-center text-gray-400">Loading...</p>
    </template>
    
    <template x-if="!historyLoading && workoutHistory.length === 0">
        <p class="text-center text-gray-400">No workouts yet</p>
    </template>
    
    <template x-for="workout in workoutHistory" :key="workout.id">
        <div 
            @click="selectedWorkout = workout"
            class="bg-gray-800 rounded-xl p-4 cursor-pointer hover:bg-gray-750"
        >
            <div class="flex justify-between items-start">
                <div>
                    <p class="font-semibold" x-text="formatDate(workout.completed_at)"></p>
                    <p class="text-gray-400 text-sm">
                        <span x-text="workout.stats.exercise_count"></span> exercises · 
                        <span x-text="workout.stats.total_sets"></span> sets
                    </p>
                </div>
                <p class="text-green-400 font-mono" x-text="formatVolume(workout.stats.total_volume)"></p>
            </div>
        </div>
    </template>
</div>

<!-- Workout Detail Modal -->
<div 
    x-show="selectedWorkout" 
    @click.self="selectedWorkout = null"
    class="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50"
>
    <div class="bg-gray-800 rounded-xl p-6 w-full max-w-md max-h-[80vh] overflow-y-auto">
        <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-bold" x-text="formatDate(selectedWorkout?.completed_at)"></h3>
            <button @click="selectedWorkout = null" class="text-gray-400">✕</button>
        </div>
        
        <template x-for="exercise in selectedWorkout?.exercises" :key="exercise.exercise_id">
            <div class="mb-4">
                <h4 class="font-semibold text-blue-400" x-text="getExerciseName(exercise.exercise_id)"></h4>
                <template x-for="(set, idx) in exercise.sets" :key="idx">
                    <p class="text-gray-300 ml-4">
                        Set <span x-text="idx + 1"></span>: 
                        <span x-text="set.weight"></span><span x-text="set.unit"></span> × 
                        <span x-text="set.reps"></span>
                    </p>
                </template>
            </div>
        </template>
    </div>
</div>
```

Update `frontend/js/app.js` - add history methods:

```javascript
function workoutApp() {
    return {
        // State
        activeTab: 'workout',
        currentWorkout: null,
        workoutHistory: [],
        historyLoading: false,
        selectedWorkout: null,
        exercises: [],
        statusMessage: '',
        statusType: 'success',
        
        async init() {
            await this.loadExercises();
            await this.loadCurrentWorkout();
        },
        
        async loadExercises() {
            try {
                const response = await fetch('/api/exercises');
                this.exercises = await response.json();
            } catch (error) {
                console.error('Failed to load exercises:', error);
            }
        },
        
        async loadHistory() {
            this.historyLoading = true;
            try {
                const response = await fetch('/api/history');
                this.workoutHistory = await response.json();
            } catch (error) {
                console.error('Failed to load history:', error);
            }
            this.historyLoading = false;
        },
        
        getExerciseName(exerciseId) {
            const ex = this.exercises.find(e => e.id === exerciseId);
            return ex ? ex.name : exerciseId;
        },
        
        formatDate(isoString) {
            if (!isoString) return '';
            const date = new Date(isoString);
            return date.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric'
            });
        },
        
        formatVolume(volume) {
            if (volume >= 1000) {
                return (volume / 1000).toFixed(1) + 'k kg';
            }
            return volume + ' kg';
        },
        
        // ... existing methods ...
    };
}
```

### Sprint 3: Test Criteria

1. Complete 2-3 workouts with exercises and sets
2. Go to History tab
3. See list of past workouts with stats
4. Tap a workout to see details
5. Verify all exercises and sets are shown

---

## Sprint 4: Templates

### Goal
Save and reuse workout structures.

### Duration: 1 day

### Dependencies: Sprint 2 complete

### Deliverables

#### 4.1 Template Projection Handler

Update `backend/events.py`:

```python
elif event_type == EventType.TEMPLATE_CREATED:
    templates = get_projection("templates", user_id) or []
    template = {
        "id": payload["template_id"],
        "name": payload["name"],
        "exercise_ids": payload["exercise_ids"],
        "created_at": datetime.utcnow().isoformat() + "Z",
        "last_used_at": None,
        "use_count": 0
    }
    templates.append(template)
    set_projection("templates", templates, user_id)

elif event_type == EventType.TEMPLATE_UPDATED:
    templates = get_projection("templates", user_id) or []
    template_id = payload["template_id"]
    for t in templates:
        if t["id"] == template_id:
            if payload.get("name"):
                t["name"] = payload["name"]
            if payload.get("exercise_ids"):
                t["exercise_ids"] = payload["exercise_ids"]
            break
    set_projection("templates", templates, user_id)

elif event_type == EventType.TEMPLATE_DELETED:
    templates = get_projection("templates", user_id) or []
    template_id = payload["template_id"]
    templates = [t for t in templates if t["id"] != template_id]
    set_projection("templates", templates, user_id)

# Also update WorkoutStarted to track template usage:
elif event_type == EventType.WORKOUT_STARTED:
    # ... existing code ...
    
    # Track template usage
    from_template_id = payload.get("from_template_id")
    if from_template_id:
        templates = get_projection("templates", user_id) or []
        for t in templates:
            if t["id"] == from_template_id:
                t["last_used_at"] = datetime.utcnow().isoformat() + "Z"
                t["use_count"] = t.get("use_count", 0) + 1
                break
        set_projection("templates", templates, user_id)
```

#### 4.2 Templates API (`backend/api/templates.py`)

```python
"""Template endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from uuid import uuid4

from backend.database import get_projection
from backend.events import emit_event
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
    templates = get_projection("templates", "default") or []
    return templates

@router.post("", response_model=TemplateResponse)
async def create_template(request: CreateTemplateRequest):
    """Create a new template."""
    template_id = str(uuid4())
    emit_event(
        EventType.TEMPLATE_CREATED,
        {
            "template_id": template_id,
            "name": request.name,
            "exercise_ids": request.exercise_ids
        },
        "default"
    )
    templates = get_projection("templates", "default") or []
    return next(t for t in templates if t["id"] == template_id)

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """Get a template by ID."""
    templates = get_projection("templates", "default") or []
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """Delete a template."""
    emit_event(
        EventType.TEMPLATE_DELETED,
        {"template_id": template_id},
        "default"
    )
    return {"success": True}

@router.post("/{template_id}/start")
async def start_from_template(template_id: str):
    """Start a new workout from a template."""
    templates = get_projection("templates", "default") or []
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
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
```

Register in `backend/main.py`:

```python
from backend.api.templates import router as templates_router
app.include_router(templates_router)
```

#### 4.3 Frontend: Template UI

Add to `frontend/index.html`:

```html
<!-- Save as Template Button (in workout view, before Finish) -->
<button 
    @click="showSaveTemplateModal = true"
    class="w-full bg-purple-600 hover:bg-purple-700 text-white font-bold py-3 px-6 rounded-xl transition-colors mb-4"
    x-show="currentWorkout && currentWorkout.exercises.length > 0"
>
    Save as Template
</button>

<!-- Save Template Modal -->
<div 
    x-show="showSaveTemplateModal" 
    @click.self="showSaveTemplateModal = false"
    class="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50"
>
    <div class="bg-gray-800 rounded-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-bold mb-4">Save as Template</h3>
        <input 
            type="text"
            x-model="templateName"
            placeholder="Template name (e.g., Push Day)"
            class="w-full bg-gray-700 rounded-lg px-4 py-3 mb-4"
        >
        <div class="flex gap-4">
            <button 
                @click="showSaveTemplateModal = false"
                class="flex-1 bg-gray-600 py-3 rounded-xl"
            >
                Cancel
            </button>
            <button 
                @click="saveAsTemplate()"
                class="flex-1 bg-purple-600 py-3 rounded-xl"
            >
                Save
            </button>
        </div>
    </div>
</div>

<!-- Start from Template Option -->
<div x-show="!currentWorkout" class="mt-4">
    <button 
        @click="showTemplatesModal = true; loadTemplates()"
        class="w-full bg-gray-700 hover:bg-gray-600 text-white py-3 px-6 rounded-xl"
    >
        Start from Template
    </button>
</div>

<!-- Templates List Modal -->
<div 
    x-show="showTemplatesModal" 
    @click.self="showTemplatesModal = false"
    class="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50"
>
    <div class="bg-gray-800 rounded-xl p-6 w-full max-w-md max-h-[80vh] overflow-y-auto">
        <h3 class="text-lg font-bold mb-4">Your Templates</h3>
        
        <template x-if="templates.length === 0">
            <p class="text-gray-400">No templates yet</p>
        </template>
        
        <template x-for="template in templates" :key="template.id">
            <div 
                @click="startFromTemplate(template.id)"
                class="bg-gray-700 rounded-lg p-4 mb-2 cursor-pointer hover:bg-gray-600"
            >
                <p class="font-semibold" x-text="template.name"></p>
                <p class="text-gray-400 text-sm">
                    <span x-text="template.exercise_ids.length"></span> exercises
                </p>
            </div>
        </template>
        
        <button 
            @click="showTemplatesModal = false"
            class="w-full mt-4 bg-gray-600 py-3 rounded-xl"
        >
            Cancel
        </button>
    </div>
</div>
```

Add to `frontend/js/app.js`:

```javascript
// Add to state
templates: [],
showSaveTemplateModal: false,
showTemplatesModal: false,
templateName: '',

// Add methods
async loadTemplates() {
    try {
        const response = await fetch('/api/templates');
        this.templates = await response.json();
    } catch (error) {
        console.error('Failed to load templates:', error);
    }
},

async saveAsTemplate() {
    if (!this.templateName.trim() || !this.currentWorkout) return;
    
    const exerciseIds = this.currentWorkout.exercises.map(e => e.exercise_id);
    
    try {
        await fetch('/api/templates', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: this.templateName.trim(),
                exercise_ids: exerciseIds
            })
        });
        this.showStatus('Template saved!', 'success');
        this.showSaveTemplateModal = false;
        this.templateName = '';
    } catch (error) {
        this.showStatus('Failed to save template', 'error');
    }
},

async startFromTemplate(templateId) {
    try {
        await fetch(`/api/templates/${templateId}/start`, {method: 'POST'});
        await this.loadCurrentWorkout();
        this.showTemplatesModal = false;
        this.showStatus('Workout started from template!', 'success');
    } catch (error) {
        this.showStatus('Failed to start from template', 'error');
    }
},
```

### Sprint 4: Test Criteria

1. Complete a workout with 3+ exercises
2. Click "Save as Template", name it "Test Day"
3. Finish the workout
4. Click "Start from Template"
5. See "Test Day" in list
6. Select it - workout starts with exercises pre-populated

---

## Sprint 5: Voice + LLM

### Goal
Log sets by speaking.

### Duration: 2 days

### Dependencies: Sprint 2 (logging), Sprint 3 (history for "same as last time")

### Environment Note: LLM Fallback Mode

If `OPENAI_API_KEY` is not set, the app runs in **manual-only mode**:
- Voice UI elements are hidden
- All logging happens through the manual UI
- This allows testing without API keys during development

To enable voice features, set the environment variable:
```bash
export OPENAI_API_KEY="your-key-here"
```

### Deliverables

#### 5.1 LLM Integration (`backend/llm.py`)

```python
"""LLM integration for voice command processing."""
import os
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI

from backend.config import OPENAI_API_KEY, LLM_MODEL, LLM_MAX_TOKENS
from backend.database import get_projection, get_exercises

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

SYSTEM_PROMPT = """You are a voice assistant for a gym workout tracker. Users speak commands to log their strength training exercises.

## Current Context
- Active workout: {workout_status}
- Focus exercise: {focus_exercise}
- Exercises in workout: {exercise_list}
- User's preferred unit: {preferred_unit}

## Available Tools
1. emit(event_type, payload) - Create a workout event
2. query(projection_key) - Get current state

## Event Types
- WorkoutStarted: Start a new workout
- SetLogged: Log a set (requires exercise_id, weight, reps, unit)
- ExerciseAdded: Add exercise without logging a set
- WorkoutCompleted: Finish the workout

## Guidelines
1. For logging sets: emit SetLogged with exercise_id, weight, reps, unit
2. If user doesn't name exercise, use focus_exercise
3. For "same as last time": query exercise_history first
4. For "add 5 pounds": query history, calculate new weight
5. Be concise

## Examples
- "Bench press 100 for 8" → emit SetLogged {exercise_id: "bench-press", weight: 100, reps: 8, unit: "kg"}
- "100 for 8" (with focus) → emit SetLogged {exercise_id: <focus>, weight: 100, reps: 8, unit: "kg"}
- "I'm done" → emit WorkoutCompleted
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "emit",
            "description": "Emit a workout event",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": ["WorkoutStarted", "SetLogged", "ExerciseAdded", "WorkoutCompleted", "WorkoutDiscarded"]
                    },
                    "payload": {
                        "type": "object",
                        "description": "Event payload"
                    }
                },
                "required": ["event_type", "payload"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query",
            "description": "Query a projection for current state",
            "parameters": {
                "type": "object",
                "properties": {
                    "projection_key": {
                        "type": "string",
                        "description": "Projection key like 'current_workout' or 'exercise_history:bench-press'"
                    }
                },
                "required": ["projection_key"]
            }
        }
    }
]

def build_context(user_id: str = "default") -> Dict[str, str]:
    """Build context for the LLM prompt."""
    current = get_projection("current_workout", user_id)
    exercises = get_exercises(user_id)
    
    if current:
        workout_status = f"Active (ID: {current['id'][:8]})"
        focus = current.get("focus_exercise", "None")
        ex_list = ", ".join(e["exercise_id"] for e in current.get("exercises", []))
    else:
        workout_status = "None"
        focus = "None"
        ex_list = "None"
    
    return {
        "workout_status": workout_status,
        "focus_exercise": focus,
        "exercise_list": ex_list or "None",
        "preferred_unit": "kg"  # TODO: Get from user settings
    }

def process_voice_command(
    transcript: str,
    user_id: str = "default"
) -> Dict[str, Any]:
    """Process a voice command transcript using LLM."""
    if not client:
        return {
            "success": False,
            "error": "LLM not configured. Set OPENAI_API_KEY.",
            "fallback": True,
            "transcript": transcript
        }
    
    context = build_context(user_id)
    prompt = SYSTEM_PROMPT.format(**context)
    
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript}
            ],
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=LLM_MAX_TOKENS
        )
        
        message = response.choices[0].message
        
        # Check for tool calls
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            return {
                "success": True,
                "action": function_name,
                "arguments": arguments,
                "message": message.content or ""
            }
        else:
            # No tool call, just a message
            return {
                "success": True,
                "action": None,
                "message": message.content or "I didn't understand that command."
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "fallback": True,
            "transcript": transcript
        }
```

#### 5.2 Voice API Endpoint (`backend/api/voice.py`)

```python
"""Voice processing endpoint."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.llm import process_voice_command
from backend.events import emit_event
from backend.schema.events import EventType
from backend.database import get_projection

router = APIRouter(prefix="/api/voice", tags=["voice"])

class VoiceRequest(BaseModel):
    transcript: str

class VoiceResponse(BaseModel):
    success: bool
    action: Optional[str] = None
    event_result: Optional[Dict[str, Any]] = None
    message: str
    fallback: bool = False
    transcript: Optional[str] = None

@router.post("/process", response_model=VoiceResponse)
async def process_voice(request: VoiceRequest):
    """Process a voice command transcript."""
    result = process_voice_command(request.transcript, "default")
    
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
        
        try:
            event_type = EventType(event_type_str)
            event_record, derived = emit_event(event_type, payload, "default")
            
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
```

Register in `backend/main.py`:

```python
from backend.api.voice import router as voice_router
app.include_router(voice_router)
```

#### 5.3 Frontend: Voice Integration (`frontend/js/voice.js`)

```javascript
/**
 * Web Speech API integration for voice input.
 */
const VoiceInput = {
    recognition: null,
    isListening: false,
    onResult: null,
    onError: null,
    
    init() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            console.warn('Speech recognition not supported');
            return false;
        }
        
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';
        
        this.recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            if (this.onResult) {
                this.onResult(transcript);
            }
        };
        
        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.isListening = false;
            if (this.onError) {
                this.onError(event.error);
            }
        };
        
        this.recognition.onend = () => {
            this.isListening = false;
        };
        
        return true;
    },
    
    start() {
        if (!this.recognition) {
            if (!this.init()) {
                return false;
            }
        }
        
        try {
            this.recognition.start();
            this.isListening = true;
            return true;
        } catch (e) {
            console.error('Failed to start recognition:', e);
            return false;
        }
    },
    
    stop() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
            this.isListening = false;
        }
    }
};
```

#### 5.4 Frontend: Voice Button UI

Add to `frontend/index.html`:

```html
<!-- Voice Button (floating) -->
<button 
    x-show="currentWorkout"
    @click="toggleVoice()"
    :class="{
        'bg-red-600 animate-pulse': isListening,
        'bg-blue-600 hover:bg-blue-700': !isListening
    }"
    class="fixed bottom-24 right-4 w-16 h-16 rounded-full flex items-center justify-center text-2xl shadow-lg z-40"
>
    🎤
</button>

<!-- Voice Feedback -->
<div 
    x-show="voiceTranscript"
    class="fixed bottom-44 left-4 right-4 bg-gray-800 rounded-xl p-4 z-40"
>
    <p class="text-gray-400 text-sm">Heard:</p>
    <p class="font-semibold" x-text="voiceTranscript"></p>
    <div class="flex gap-2 mt-2" x-show="voiceFallback">
        <button @click="retryVoice()" class="flex-1 bg-blue-600 py-2 rounded-lg">🎤 Retry</button>
        <button @click="clearVoice()" class="flex-1 bg-gray-600 py-2 rounded-lg">✕ Cancel</button>
    </div>
</div>
```

Add to `frontend/js/app.js`:

```javascript
// Add to state
isListening: false,
voiceTranscript: '',
voiceFallback: false,
voiceSupported: false,

// Add to init
async init() {
    this.voiceSupported = VoiceInput.init();
    VoiceInput.onResult = (transcript) => this.handleVoiceResult(transcript);
    VoiceInput.onError = (error) => this.handleVoiceError(error);
    // ... existing init code
},

// Add methods
toggleVoice() {
    if (this.isListening) {
        VoiceInput.stop();
        this.isListening = false;
    } else {
        if (VoiceInput.start()) {
            this.isListening = true;
            this.voiceTranscript = '';
            this.voiceFallback = false;
        } else {
            this.showStatus('Voice not supported in this browser', 'error');
        }
    }
},

async handleVoiceResult(transcript) {
    this.isListening = false;
    this.voiceTranscript = transcript;
    
    try {
        const response = await fetch('/api/voice/process', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({transcript})
        });
        
        const result = await response.json();
        
        if (result.success) {
            this.showStatus(result.message, 'success');
            this.voiceTranscript = '';
            await this.loadCurrentWorkout();
        } else if (result.fallback) {
            this.voiceFallback = true;
            this.showStatus('Could not process. Please try again or enter manually.', 'error');
        } else {
            this.showStatus(result.message, 'error');
        }
    } catch (error) {
        this.showStatus('Failed to process voice command', 'error');
        this.voiceFallback = true;
    }
},

handleVoiceError(error) {
    this.isListening = false;
    this.showStatus('Voice error: ' + error, 'error');
},

retryVoice() {
    this.voiceTranscript = '';
    this.voiceFallback = false;
    this.toggleVoice();
},

clearVoice() {
    this.voiceTranscript = '';
    this.voiceFallback = false;
},
```

### Sprint 5: Test Criteria

1. Set OPENAI_API_KEY environment variable
2. Start a workout
3. Tap mic button, say "Bench press 100 for 8"
4. See confirmation, set logged
5. Tap mic, say "100 for 8" (uses focus)
6. Tap mic, say "I'm done"
7. Workout finishes

---

## Sprint 6: Smart Features

### Goal
PR detection, previous values, "same as last time"

### Duration: 1 day

### Dependencies: Sprint 3 (history), Sprint 5 (voice)

### Key Deliverables

1. **Exercise history projection** - Track sets per exercise across all workouts
2. **PR detection** - Compare new sets against history
3. **Previous values display** - Show last workout's values when adding exercise
4. **LLM support** - Handle "same as last time", "add 5 pounds"

Implementation details are similar to previous sprints. Key additions:

- Add `exercise_history` projection (exercise_id → list of sessions with sets)
- Add `personal_records` projection (exercise_id → best set)
- Update SetLogged handler to check for PRs
- Update UI to show previous values
- Update LLM prompt with history context

---

## Sprint 7: Tutorial

### Goal
Guided mock workout for new users

### Duration: 1 day

### Dependencies: Sprint 5 (voice), Sprint 6 (smart features)

### Key Deliverables

1. **Tutorial state machine** - 9-step flow
2. **Sandbox mode** - Events not persisted (use `X-Tutorial-Mode: true` header)
3. **Tutorial UI overlay** - Prompts and guidance
4. **First-launch detection** - Show tutorial option

See `technical_specification.md` "Interactive Tutorial System" section for full implementation details.

### Important: Sandbox Cleanup

When tutorial completes (step 9 or user exits early), **always clean up sandbox state**:

```python
# In tutorial completion endpoint
def complete_tutorial(user_id: str):
    # Clear server-side sandbox data
    clear_sandbox_events(user_id)
    
    # Tell frontend to clear localStorage tutorial state
    return {"status": "complete", "clear_local_state": True}
```

```javascript
// In frontend
async function completeTutorial() {
    const response = await fetch('/api/tutorial/complete', { method: 'POST' });
    const data = await response.json();
    
    if (data.clear_local_state) {
        localStorage.removeItem('tutorial_step');
        localStorage.removeItem('tutorial_started');
    }
    
    // Redirect to normal mode
    window.location.href = '/';
}
```

This prevents sandbox state from accidentally leaking into normal workout mode.

---

## Sprint 8: Analytics + Export + Polish

### Goal
Progress visualization, data export, UX polish

### Duration: 2 days

### Dependencies: Sprint 3 (history), Sprint 6 (PRs)

### Key Deliverables

1. **Time-based aggregates** - Daily, weekly, monthly stats
2. **Volume chart** - Line chart of weekly volume
3. **Exercise progress chart** - Max weight over time per exercise
4. **CSV export** - Download all workout data
5. **PWA manifest** - "Add to Home Screen"
6. **Theme toggle** - Dark/light mode
7. **Performance optimization** - Lazy loading, caching

---

## Summary: Sprint Dependencies

```
Sprint 1 (Skeleton)
    └── Sprint 2 (Logging)
            ├── Sprint 3 (History)
            │       └── Sprint 6 (Smart) ─────┐
            │                                  ├── Sprint 7 (Tutorial)
            ├── Sprint 4 (Templates)          │
            │                                  │
            └── Sprint 5 (Voice) ─────────────┘
                                               │
                                               └── Sprint 8 (Analytics)
```

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (for voice)
export OPENAI_API_KEY=your_key_here

# Initialize database and start server
cd /path/to/gym_app
uvicorn backend.main:app --reload --port 8000

# Open browser
open http://localhost:8000
```

## Notes for Claude Code

1. **Create files in order** - Follow the sprint sequence
2. **Test after each sprint** - Use the test criteria provided
3. **Commit after each sprint** - Keep changes atomic (see git guidance below)
4. **Ask if stuck** - Specs are detailed but not exhaustive
5. **Frontend is minimal** - Focus on function over form initially

---

## Version Control Checkpoints

Commit after each sprint to keep work incremental and reversible:

```bash
# After Sprint 1
git add -A
git commit -m "Sprint 1: Walking skeleton - start/finish workout flow"

# After Sprint 2
git add -A
git commit -m "Sprint 2: Manual workout logging - exercises, sets, UI"

# After Sprint 3
git add -A
git commit -m "Sprint 3: Workout history - view past workouts"

# After Sprint 4
git add -A
git commit -m "Sprint 4: Templates - save and reuse workout structures"

# After Sprint 5
git add -A
git commit -m "Sprint 5: Voice + LLM - log sets by speaking"

# After Sprint 6
git add -A
git commit -m "Sprint 6: Smart features - PRs, previous values, history"

# After Sprint 7
git add -A
git commit -m "Sprint 7: Tutorial - guided onboarding flow"

# After Sprint 8
git add -A
git commit -m "Sprint 8: Analytics + Export + Polish - MVP complete"
```

---

## Future Considerations (Post-MVP)

These items are explicitly out of scope for MVP but should be addressed soon after:

### API Authentication
- Currently uses hardcoded `user_id = "default"`
- Future: Add token-based auth (JWT)
- Future: Scope all database operations by authenticated user
- Future: Rate limiting on public endpoints

### History Pagination
- Current implementation loads entire workout history into projection
- Works fine for <500 workouts
- Future: Add server-side pagination (`?page=1&limit=20`)
- Future: Add date range filtering (`?from=2025-01-01&to=2025-12-31`)
- Future: Consider moving to on-demand queries instead of full projection for large histories

### Data Retention
- Events are append-only and never deleted
- Future: Consider archival strategy for very old events
- Future: Add data export scheduling (weekly backup)

