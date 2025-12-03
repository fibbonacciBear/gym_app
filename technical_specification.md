# Voice-First Workout Tracker – Technical Specification

## Overview

This document defines the technical architecture for implementing the voice-first workout tracker. The system uses **event sourcing** for data persistence, **LLM-powered voice processing**, and a **schema-driven approach** that enables flexible evolution of features.

### Design Principles

1. **Event Sourcing** - All changes are immutable events; current state is derived
2. **Schema-Driven** - Single schema defines events, validation, and LLM behavior
3. **Voice Writes, UI Reads** - Voice input creates events; UI displays projections
4. **Data Ownership** - User data stored locally, fully exportable

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BROWSER (User Interface)                            │
│                                                                             │
│   ┌─────────────────────────────────────┐    ┌────────────────────────────┐ │
│   │   Voice Input                       │    │   Display (UI)             │ │
│   │                                     │    │   • Current Workout        │ │
│   │   ┌─────────────────────────────┐   │    │   • History                │ │
│   │   │  Microphone                 │   │    │   • Progress Charts        │ │
│   │   │  "Bench 100 for 8"          │   │    │                            │ │
│   │   └─────────────┬───────────────┘   │    └──────────────▲─────────────┘ │
│   │                 │                   │                   │               │
│   │                 ▼                   │                   │               │
│   │   ┌─────────────────────────────┐   │                   │               │
│   │   │  Speech-to-Text             │   │                   │               │
│   │   │  (Web Speech API)           │   │                   │               │
│   │   │                             │   │                   │               │
│   │   │  Output: "bench 100 for 8"  │   │                   │               │
│   │   └─────────────┬───────────────┘   │                   │               │
│   └─────────────────┼───────────────────┘                   │               │
│                     │                                       │               │
│                     │ POST /api/voice/process               │ GET /api/*    │
│                     │ { transcript: "bench 100 for 8" }     │               │
└─────────────────────┼───────────────────────────────────────┼───────────────┘
                      │                                       │
                      ▼                                       │
┌─────────────────────────────────────────────────────────────┼───────────────┐
│                         BACKEND (FastAPI)                   │               │
│                                                             │               │
│   ┌─────────────────────────────┐    ┌────────────────────┐ │               │
│   │   Voice Processing API      │    │   Query API        │─┘               │
│   │   POST /api/voice/process   │    │   GET /projections │                 │
│   │                             │    │   GET /aggregates  │                 │
│   │   Receives: transcript      │    │   GET /stats       │                 │
│   └─────────────┬───────────────┘    └────────────────────┘                 │
│                 │                              ▲                            │
│                 ▼                              │                            │
│   ┌─────────────────────────────┐              │                            │
│   │   LLM Processing            │              │ Read                       │
│   │   (OpenAI / Claude / Local) │              │                            │
│   │                             │              │                            │
│   │   • Schema-aware            │              │                            │
│   │   • emit(event) tool        │              │                            │
│   │   • query() tool            │──────────────┘                            │
│   └─────────────┬───────────────┘                                           │
│                 │                                                           │
│                 │ emit(event)                                               │
│                 ▼                                                           │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         EVENT STORE                                 │   │
│   │                    (SQLite - Append Only)                           │   │
│   │                                                                     │   │
│   │  #1 WorkoutStarted { workout_id: "w1" }                             │   │
│   │  #2 SetLogged { workout_id: "w1", exercise: "bench", weight: 100 }  │   │
│   │  #3 SetLogged { workout_id: "w1", exercise: "bench", weight: 100 }  │   │
│   │  #4 WorkoutCompleted { workout_id: "w1" }                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   │ Events trigger projection updates       │
│                                   ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       PROJECTIONS & AGGREGATES                      │   │
│   │                                                                     │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐ │   │
│   │  │   Current    │  │   Exercise   │  │   Time-Based Aggregates   │ │   │
│   │  │   Workout    │  │   History    │  │   • daily_stats           │ │   │
│   │  └──────────────┘  └──────────────┘  │   • weekly_stats          │ │   │
│   │  ┌──────────────┐  ┌──────────────┐  │   • monthly_stats         │ │   │
│   │  │   Personal   │  │   Workout    │  │   • yearly_stats          │ │   │
│   │  │   Records    │  │   History    │  └───────────────────────────┘ │   │
│   │  └──────────────┘  └──────────────┘                                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FILE SYSTEM                                    │
│                                                                             │
│   /workspace/{user_id}/                                                     │
│   └── gym.db                    ← SQLite database                           │
│       ├── events table          (append-only event log)                     │
│       ├── projections table     (current state views)                       │
│       ├── aggregates table      (time-based statistics)                     │
│       └── exercises table       (exercise library)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

| Step | Location | What Happens |
|------|----------|--------------|
| 1 | Browser | User taps mic, speaks "Bench 100 for 8" |
| 2 | Browser | Web Speech API converts speech → text |
| 3 | Browser → Backend | POST transcript to `/api/voice/process` |
| 4 | Backend | LLM interprets, calls `emit(SetLogged, {...})` |
| 5 | Backend | Event validated, stored, projections updated |
| 6 | Backend → Browser | Response with confirmation + PR flag |
| 7 | Browser | UI updates to show new set |

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Backend** | FastAPI (Python 3.11+) | Async, type hints, auto-generated OpenAPI docs |
| **Database** | SQLite with JSON columns | Single file, ACID, portable, JSON querying |
| **Frontend** | HTML + Tailwind CSS + Alpine.js | No build step, fast prototyping, lightweight |
| **Voice STT** | Web Speech API | Browser-native, no external dependencies |
| **LLM** | OpenAI GPT-4o-mini / Claude Haiku | Fast, cheap, excellent tool calling |
| **Charts** | Chart.js or Lightweight alternative | Simple, responsive, no heavy dependencies |

---

## Event Sourcing Model

### Core Concepts

| Concept | Description |
|---------|-------------|
| **Event** | Immutable fact that something happened (e.g., "SetLogged") |
| **Event Store** | Append-only log of all events |
| **Projection** | Current state derived from events (e.g., "current_workout") |
| **Aggregate** | Pre-computed statistics over time periods |

### Event Flow

```
User Action          Event Created           Projections Updated
───────────          ─────────────           ───────────────────
"Start workout"  →   WorkoutStarted      →   current_workout = {...}
"Bench 100×8"    →   SetLogged           →   current_workout.sets.push(...)
                                             exercise_history["bench"].push(...)
                                             check_and_update_pr(...)
"I'm done"       →   WorkoutCompleted    →   current_workout = null
                                             workout_history.push(...)
                                             update_daily_stats(...)
                                             update_weekly_stats(...)
```

### Why Event Sourcing?

| Benefit | How It Helps |
|---------|--------------|
| **Complete History** | "What did I lift last Tuesday?" - Query event log |
| **Undo/Redo** | Emit compensating events, never lose data |
| **Debugging** | Replay events to reproduce any issue |
| **Analytics** | All data points preserved for any future analysis |
| **Audit Trail** | Events ARE the audit log |
| **Offline Sync** | Queue events locally, sync when online |

---

## Workout Building Flows

The system supports two distinct workflows for building a workout session.

### Flow A: Voice-First (Implicit Exercise Addition)

User speaks commands, exercises are added automatically when first mentioned.

```
User: "Start a workout"
  → emit(WorkoutStarted)
  → current_workout = { id: "w1", exercises: [], focus_exercise: null }

User: "Bench press 100 for 8"
  → Exercise "bench-press" not in workout, so implicitly add it
  → emit(SetLogged, { exercise_id: "bench-press", weight: 100, reps: 8 })
  → current_workout.exercises = [{ id: "bench-press", sets: [...] }]
  → current_workout.focus_exercise = "bench-press"

User: "100 for 8"  (no exercise named)
  → Use focus_exercise ("bench-press")
  → emit(SetLogged, { exercise_id: "bench-press", weight: 100, reps: 8 })

User: "Squat 140 for 5"
  → New exercise mentioned, implicitly add it
  → emit(SetLogged, { exercise_id: "squat", weight: 140, reps: 5 })
  → current_workout.focus_exercise = "squat"  (focus shifts)
```

### Flow B: UI-First (Explicit Exercise Addition)

User builds exercise list via UI, then logs sets.

```
User: Taps "Start Workout"
  → emit(WorkoutStarted)

User: Taps "+" → Selects "Bench Press"
  → emit(ExerciseAdded, { exercise_id: "bench-press" })
  → current_workout.exercises = [{ id: "bench-press", sets: [] }]

User: Taps "+" → Selects "Squat"
  → emit(ExerciseAdded, { exercise_id: "squat" })

User: Taps on "Bench Press" row
  → current_workout.focus_exercise = "bench-press" (UI selection)

User: Enters 100kg, 8 reps, taps "Add Set"
  → emit(SetLogged, { exercise_id: "bench-press", weight: 100, reps: 8 })
```

### Focus Exercise

The `focus_exercise` field in the current workout projection tracks which exercise receives sets when the user doesn't explicitly name one.

```yaml
# current_workout projection structure
current_workout:
  id: uuid
  started_at: datetime
  from_template_id: uuid | null    # ← Template used to start (if any)
  from_template_name: string | null
  focus_exercise: string | null    # ← Currently active exercise
  exercises:
    - exercise_id: string
      sets: [...]
```

**Focus persistence:** Focus is valid only for the current workout session. When the workout is completed or discarded, focus resets. Leaving the app mid-workout preserves focus (workout state is persisted).

### Templates Projection

```yaml
# templates projection structure
templates:
  - id: uuid
    name: string                    # "Push Day"
    exercise_ids: [string]          # ["bench-press", "overhead-press", ...]
    created_at: datetime
    last_used_at: datetime | null
    use_count: integer
```

Templates are queried when:
- User opens "Start from Template" UI
- User says "Start my push day" (LLM searches templates by name)
- Showing "last time on this template" values

**Future consideration:** If exercises are renamed or deleted, templates referencing them may break. Consider adding:
- `version` field for template schema migrations
- `archived` flag for soft-delete
- Exercise ID validation on template load (skip missing exercises with warning)

**Focus changes when:**

| Action | Effect on Focus |
|--------|-----------------|
| Voice: "Bench press 100 for 8" | Focus = "bench-press" |
| Voice: "100 for 8" (shorthand) | Focus unchanged, set added to current focus |
| UI: Tap exercise row | Focus = tapped exercise |
| UI: Add new exercise | Focus = newly added exercise |
| Voice: "Add squats" | Focus = "squat" |

**LLM behavior with focus:**

```
Context provided to LLM:
- focus_exercise: "bench-press"

User says: "100 for 8"
LLM interprets: Log set for bench-press (the focus)

User says: "Another set same weight"
LLM interprets: Query history for bench-press, log same weight
```

### Implicit vs Explicit Exercise Addition

| Event | When Used |
|-------|-----------|
| `ExerciseAdded` | User explicitly adds via UI or says "Add squats" |
| `SetLogged` (exercise not in workout) | Exercise implicitly added when logging first set |

Both result in the exercise appearing in the workout. The difference is intentionality:
- Explicit: User wants to structure workout before logging
- Implicit: User just wants to log, system handles structure

**Backend logic for SetLogged:**

```python
def handle_set_logged(event, current_workout):
    exercise_id = event.payload["exercise_id"]
    
    # Check if exercise already in workout
    existing = find_exercise_in_workout(current_workout, exercise_id)
    
    if not existing:
        # Implicitly add exercise to workout
        current_workout.exercises.append({
            "exercise_id": exercise_id,
            "sets": []
        })
    
    # Add the set
    exercise = find_exercise_in_workout(current_workout, exercise_id)
    exercise.sets.append(event.payload)
    
    # Update focus
    current_workout.focus_exercise = exercise_id
```

---

## Schema Definitions

The schema is the **single source of truth** for data validation, LLM behavior, and UI generation.

### Event Schema

```yaml
# schema/events.yaml
version: "1.0"

events:
  WorkoutStarted:
    description: "User begins a new workout session"
    payload:
      workout_id:
        type: uuid
        auto: true
        description: "Unique identifier for this workout"
      name:
        type: string
        optional: true
        description: "Optional workout name (e.g., 'Push Day')"
      from_template_id:
        type: uuid
        optional: true
        description: "If starting from template, the template ID"
      exercise_ids:
        type: array
        items: string
        optional: true
        description: "Pre-populated exercises (from template or explicit)"
        
  ExerciseAdded:
    description: "User adds an exercise to the current workout"
    payload:
      workout_id:
        type: uuid
        required: true
      exercise_id:
        type: string
        required: true
        description: "Reference to exercise library"
        
  SetLogged:
    description: "User logs a set for an exercise"
    payload:
      workout_id:
        type: uuid
        required: true
      exercise_id:
        type: string
        required: true
      weight:
        type: number
        required: true
        min: 0
        description: "Weight lifted"
      reps:
        type: integer
        required: true
        min: 0
        description: "Number of repetitions"
      unit:
        type: string
        enum: [kg, lb]
        default: "$user.settings.preferred_unit"
        
  SetModified:
    description: "User corrects a previous set"
    payload:
      original_event_id:
        type: uuid
        required: true
        description: "The SetLogged event being modified"
      weight:
        type: number
        optional: true
      reps:
        type: integer
        optional: true
      unit:
        type: string
        enum: [kg, lb]
        optional: true
        
  SetDeleted:
    description: "User removes a set"
    payload:
      original_event_id:
        type: uuid
        required: true
        description: "The SetLogged event being deleted"
      reason:
        type: string
        optional: true
        
  WorkoutCompleted:
    description: "User finishes the workout"
    payload:
      workout_id:
        type: uuid
        required: true
      notes:
        type: string
        optional: true
        
  WorkoutDiscarded:
    description: "User cancels the workout without saving"
    payload:
      workout_id:
        type: uuid
        required: true
      reason:
        type: string
        optional: true
        
  # Template Events
  TemplateCreated:
    description: "User saves a workout structure as a reusable template"
    payload:
      template_id:
        type: uuid
        auto: true
      name:
        type: string
        required: true
        description: "Template name (e.g., 'Push Day', 'Leg Day')"
      exercise_ids:
        type: array
        items: string
        required: true
        description: "Ordered list of exercise IDs in this template"
      source_workout_id:
        type: uuid
        optional: true
        description: "Workout this template was created from (if any)"
        
  TemplateUpdated:
    description: "User modifies a template"
    payload:
      template_id:
        type: uuid
        required: true
      name:
        type: string
        optional: true
      exercise_ids:
        type: array
        items: string
        optional: true
        
  TemplateDeleted:
    description: "User deletes a template"
    payload:
      template_id:
        type: uuid
        required: true
```

### Entity Schema

```yaml
# schema/entities.yaml
version: "1.0"

entities:
  Exercise:
    description: "An exercise that can be performed"
    fields:
      id:
        type: string
        primary: true
        format: slug
        description: "URL-safe identifier (e.g., 'bench-press')"
      name:
        type: string
        required: true
        description: "Display name"
      category:
        type: string
        enum: [chest, back, shoulders, arms, legs, core, cardio, other]
        description: "Muscle group"
      description:
        type: string
        optional: true
      is_custom:
        type: boolean
        default: false
        description: "True if user-created"
        
  UserSettings:
    description: "User preferences"
    singleton: true
    fields:
      preferred_unit:
        type: string
        enum: [kg, lb]
        default: kg
      rest_timer_seconds:
        type: integer
        default: 90
        min: 0
        max: 600
      theme:
        type: string
        enum: [dark, light, system]
        default: dark
```

### Aggregate Schema

```yaml
# schema/aggregates.yaml
version: "1.0"

aggregates:
  DailyStats:
    description: "Statistics for a single day"
    key_format: "YYYY-MM-DD"
    fields:
      date:
        type: date
      workout_count:
        type: integer
      total_sets:
        type: integer
      total_reps:
        type: integer
      total_volume:
        type: number
        description: "Sum of (weight × reps)"
      exercises:
        type: array
        items: string
      prs_hit:
        type: integer
      duration_minutes:
        type: integer
        
  WeeklyStats:
    description: "Statistics for a week (ISO week)"
    key_format: "YYYY-Www"
    fields:
      week:
        type: string
      start_date:
        type: date
      end_date:
        type: date
      workout_count:
        type: integer
      total_sets:
        type: integer
      total_volume:
        type: number
      avg_workout_duration:
        type: number
      muscle_group_breakdown:
        type: object
        description: "Volume by muscle group"
      prs_hit:
        type: integer
      vs_previous:
        type: object
        fields:
          volume_change_pct:
            type: number
          workout_count_change:
            type: integer
            
  MonthlyStats:
    description: "Statistics for a month"
    key_format: "YYYY-MM"
    fields:
      month:
        type: string
      workout_count:
        type: integer
      total_volume:
        type: number
      avg_workouts_per_week:
        type: number
      most_trained_exercises:
        type: array
        items:
          type: object
          fields:
            exercise_id: string
            sets: integer
            volume: number
      prs_hit:
        type: integer
      streak_days:
        type: integer
      best_streak_days:
        type: integer
        
  YearlyStats:
    description: "Statistics for a year"
    key_format: "YYYY"
    fields:
      year:
        type: integer
      workout_count:
        type: integer
      total_volume:
        type: number
      total_prs:
        type: integer
      exercises_tried:
        type: integer
      favorite_exercises:
        type: array
        items:
          type: object
          fields:
            exercise_id: string
            sessions: integer
      monthly_volume_trend:
        type: array
        items:
          type: object
          fields:
            month: string
            volume: number
```

---

## Database Design (SQLite)

### Tables

```sql
-- Event store (append-only)
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,        -- UUID
    timestamp TEXT NOT NULL,               -- ISO 8601 datetime
    event_type TEXT NOT NULL,              -- 'WorkoutStarted', 'SetLogged', etc.
    payload TEXT NOT NULL,                 -- JSON payload
    schema_version INTEGER DEFAULT 1       -- For future migrations
);

CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_workout ON events(json_extract(payload, '$.workout_id'));

-- Projections (rebuildable from events)
CREATE TABLE projections (
    key TEXT PRIMARY KEY,                  -- 'current_workout', 'exercise_history:bench-press'
    data TEXT NOT NULL,                    -- JSON
    updated_at TEXT NOT NULL               -- ISO 8601 datetime
);

-- Time-based aggregates
CREATE TABLE aggregates (
    period_type TEXT NOT NULL,             -- 'daily', 'weekly', 'monthly', 'yearly'
    period_key TEXT NOT NULL,              -- '2025-12-06', '2025-W49', '2025-12', '2025'
    data TEXT NOT NULL,                    -- JSON
    updated_at TEXT NOT NULL,
    PRIMARY KEY (period_type, period_key)
);

-- Exercise library (default + custom)
CREATE TABLE exercises (
    id TEXT PRIMARY KEY,                   -- 'bench-press'
    name TEXT NOT NULL,                    -- 'Bench Press'
    category TEXT,                         -- 'chest'
    description TEXT,
    is_custom INTEGER DEFAULT 0,
    created_at TEXT
);
```

### File Location

```
/workspace/{user_id}/
└── gym.db                    ← Single SQLite file
```

### Example Queries

```sql
-- Get all events for a workout
SELECT * FROM events 
WHERE json_extract(payload, '$.workout_id') = ?
ORDER BY timestamp;

-- Get current workout projection
SELECT data FROM projections WHERE key = 'current_workout';

-- Get this week's stats
SELECT data FROM aggregates 
WHERE period_type = 'weekly' AND period_key = '2025-W49';

-- Get exercise history for bench press
SELECT 
    json_extract(payload, '$.weight') as weight,
    json_extract(payload, '$.reps') as reps,
    timestamp
FROM events
WHERE event_type = 'SetLogged'
  AND json_extract(payload, '$.exercise_id') = 'bench-press'
ORDER BY timestamp DESC
LIMIT 20;

-- Rebuild projection from events (disaster recovery)
-- Just replay all events through the projection logic
```

---

## LLM Integration

### Architecture

```
┌──────────────────┐     ┌─────────────────────────────────────────────────────┐
│ Speech-to-Text   │     │                  LLM Processing                     │
│                  │     │                                                     │
│ "Bench 100 for 8"│────▶│  System Prompt:                                     │
│                  │     │  • Event schema (what events exist)                 │
└──────────────────┘     │  • Current context (active workout, last exercise)  │
                         │  • User preferences (units, etc.)                   │
                         │                                                     │
                         │  Available Tool:                                    │
                         │  • emit(event_type, payload)                        │
                         │  • query(projection_name)                           │
                         │                                                     │
                         │  LLM Output:                                        │
                         │  → emit("SetLogged", {                              │
                         │      exercise_id: "bench-press",                    │
                         │      weight: 100, reps: 8, unit: "kg"               │
                         │    })                                               │
                         └──────────────────────────────────────┬──────────────┘
                                                                │
                                                                ▼
                         ┌─────────────────────────────────────────────────────┐
                         │                  Backend                            │
                         │                                                     │
                         │  1. Validate event against schema                   │
                         │  2. Append to event store                           │
                         │  3. Update projections                              │
                         │  4. Update aggregates                               │
                         │  5. Return result (including is_pr flag)            │
                         └─────────────────────────────────────────────────────┘
```

### LLM Tools

```yaml
tools:
  emit:
    description: |
      Emit a workout event. Events are validated against the schema 
      and appended to the immutable event log.
    parameters:
      event_type:
        type: string
        enum: [WorkoutStarted, ExerciseAdded, SetLogged, SetModified, 
               SetDeleted, WorkoutCompleted, WorkoutDiscarded]
        required: true
      payload:
        type: object
        required: true
        description: "Event payload matching the schema for this event type"
    returns:
      event_id: "UUID of the created event"
      derived: "Any computed values (e.g., is_pr, total_volume)"
      
  query:
    description: |
      Query a projection or aggregate for current state information.
      Use this to get context before emitting events.
    parameters:
      type:
        type: string
        enum: [projection, aggregate]
        required: true
      key:
        type: string
        required: true
        description: |
          For projections: 'current_workout', 'exercise_history:{id}', 'personal_records'
          For aggregates: 'daily:2025-12-06', 'weekly:2025-W49', etc.
    returns:
      data: "The projection or aggregate data"
```

### System Prompt

```markdown
You are a voice assistant for a gym workout tracker. Users speak commands to log their strength training exercises.

## Event Schema
{events_schema_yaml}

## Current Context
- Active workout: {current_workout_id or "None"}
- Focus exercise: {focus_exercise or "None"} ← Use this for shorthand commands
- Exercises in workout: {exercise_list}
- User's preferred unit: {preferred_unit}

## Available Tools
1. `emit(event_type, payload)` - Create a new event
2. `query(type, key)` - Get current state

## Guidelines
1. For logging sets: emit a SetLogged event
2. If user doesn't name an exercise, use the focus_exercise
3. If exercise isn't in workout yet, it will be added automatically when you log a set
4. For "same as last time": query exercise_history first, then emit with those values
5. For "add 5 pounds": query history, calculate new weight, emit
6. For "add [exercise]" without weight/reps: emit ExerciseAdded (no set logged)
7. For corrections: emit SetModified or SetDeleted
8. For "start my [name] workout": query templates, emit WorkoutStarted with from_template_id
9. For "save this as [name]": emit TemplateCreated with current workout's exercises
10. Be concise - users are mid-workout

## Examples

User: "Bench press 100 kilos for 8"
→ emit("SetLogged", {exercise_id: "bench-press", weight: 100, reps: 8, unit: "kg"})
→ Response: "Logged 100kg × 8 for Bench Press"

User: "100 for 8" (focus_exercise = "bench-press")
→ emit("SetLogged", {exercise_id: "bench-press", weight: 100, reps: 8, unit: "kg"})
→ Response: "Logged 100kg × 8"

User: "Same as last time" (focus_exercise = "squat")
→ query("projection", "exercise_history:squat")
→ emit("SetLogged", {exercise_id: "squat", weight: 140, reps: 5, unit: "kg"})
→ Response: "Logged 140kg × 5 for Squat (same as last time)"

User: "Add 5 pounds"  (focus_exercise = "bench-press")
→ query("projection", "exercise_history:bench-press")  // Returns last: 100 kg
→ Convert 5 lb to kg ≈ 2.3 kg, round to 102.5 kg
→ emit("SetLogged", {exercise_id: "bench-press", weight: 102.5, reps: 8, unit: "kg"})
→ Response: "Logged 102.5kg × 8 for Bench Press (+2.5kg)"

User: "Add squats" (just add exercise, no set)
→ emit("ExerciseAdded", {exercise_id: "squat"})
→ Response: "Added Squat to workout"

User: "Delete that last set"
→ emit("SetDeleted", {original_event_id: "{last_set_event_id}"})
→ Response: "Deleted last set"

User: "I'm done"
→ emit("WorkoutCompleted", {workout_id: "{current_workout_id}", notes: ""})
→ Response: "Workout saved! 5 exercises, 18 sets, 12,500kg total volume"

User: "Start my push day workout"
→ query("projection", "templates")  // Find template named "push day"
→ emit("WorkoutStarted", {from_template_id: "tpl-123", exercise_ids: ["bench-press", "overhead-press", "tricep-pushdown"]})
→ Response: "Started Push Day workout with 3 exercises"

User: "Save this as leg day"
→ emit("TemplateCreated", {name: "Leg Day", exercise_ids: [current workout exercises]})
→ Response: "Saved as template 'Leg Day' with 4 exercises"
```

### Minimal Prompt Variant

For latency/cost optimization, a stripped-down prompt can be used for simple commands:

```markdown
You log gym sets. Tools: emit(event_type, payload), query(type, key).

Context: focus_exercise={focus}, unit={unit}

Rules:
- "X for Y" → emit SetLogged with focus_exercise
- "[exercise] X for Y" → emit SetLogged with named exercise  
- "same as last time" → query history, emit with previous values
- "I'm done" → emit WorkoutCompleted

Output: tool call only, no explanation.
```

**When to use minimal prompt:**
- User has completed tutorial (familiar with commands)
- Command matches simple patterns (set logging)
- Latency is critical (rapid set logging)

**When to use full prompt:**
- First-time or infrequent users
- Complex commands ("add 5 pounds to my last squat weight")
- Errors or ambiguous input (need better error messages)

### Example LLM Flow

```
User: "Start a workout"

LLM:
  Tool call: emit("WorkoutStarted", {})
  
Backend:
  1. Generate workout_id: "w-abc123"
  2. Validate: ✓ (no required fields)
  3. Append event to store
  4. Update projection: current_workout = {id: "w-abc123", started_at: "..."}
  5. Return: {event_id: "e-001", workout_id: "w-abc123"}

LLM Response: "Started a new workout. What's your first exercise?"

---

User: "Bench press 100 kilos 8 reps"

LLM:
  Tool call: emit("SetLogged", {
    workout_id: "w-abc123",
    exercise_id: "bench-press", 
    weight: 100, 
    reps: 8, 
    unit: "kg"
  })

Backend:
  1. Validate against schema: ✓
  2. Append event to store
  3. Update current_workout projection (add set)
  4. Update exercise_history projection
  5. Check for PR: Yes! Previous best was 95kg × 8
  6. Return: {event_id: "e-002", is_pr: true}

LLM Response: "Logged 100kg × 8 for Bench Press. That's a new PR! 🏆"
```

---

## API Endpoints

### Events API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/events` | Emit a new event |
| GET | `/api/events` | List events (with filters) |
| GET | `/api/events/{event_id}` | Get single event |

### Projections API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projections/current-workout` | Get active workout |
| GET | `/api/projections/workout-history` | List completed workouts |
| GET | `/api/projections/exercise-history/{id}` | History for one exercise |
| GET | `/api/projections/personal-records` | All PRs |

### Aggregates API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats/daily/{date}` | Stats for a day |
| GET | `/api/stats/weekly/{week}` | Stats for a week |
| GET | `/api/stats/monthly/{month}` | Stats for a month |
| GET | `/api/stats/yearly/{year}` | Stats for a year |
| GET | `/api/stats/trend` | Time-series data for charts |

### Templates API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/templates` | List all templates |
| POST | `/api/templates` | Create template (emits TemplateCreated) |
| GET | `/api/templates/{id}` | Get template details |
| PUT | `/api/templates/{id}` | Update template (emits TemplateUpdated) |
| DELETE | `/api/templates/{id}` | Delete template (emits TemplateDeleted) |
| POST | `/api/templates/{id}/start` | Start workout from template |

### Exercises API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/exercises` | List all exercises |
| POST | `/api/exercises` | Create custom exercise |
| GET | `/api/exercises/{id}` | Get exercise details |

### Voice API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/voice/process` | Process voice transcript via LLM |

### Export API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/csv` | Download all data as CSV |
| GET | `/api/export/events` | Download raw event log |

---

## Data-Driven UI

### Concept

The UI is generated from schema and configurations, not hardcoded. This enables:
- Adding fields without code changes
- Consistent validation between backend and frontend
- LLM and UI always in sync

### View Configuration Example

```yaml
# views/current_workout.yaml
view: current_workout
data_source: projections.current_workout

layout:
  - component: header
    fields: [started_at]
    format: "Started {started_at|timeago}"
    
  - component: exercise_list
    source: exercises
    item:
      - field: exercise_name
        style: title
      - component: set_list
        source: sets
        columns: [weight, reps, is_pr]
        
  - component: voice_button
    size: large
    position: floating
    
  - component: action_bar
    actions:
      - label: "Finish Workout"
        event: WorkoutCompleted
      - label: "Discard"
        event: WorkoutDiscarded
        confirm: true
```

### Analytics View Configuration

```yaml
# views/progress.yaml
view: progress
layout:
  - component: filter_bar
    filters:
      - name: exercise
        type: select
        source: exercises
      - name: period
        type: select
        options: [4w, 12w, 6m, ytd]
      - name: metric
        type: select
        options: [volume, max_weight, e1rm]
        
  - component: line_chart
    data_source: api/stats/trend
    params: [exercise, period, metric]
    
  - component: stat_grid
    columns: 3
    items:
      - label: "Total Volume"
        source: api/stats/summary
        field: total_volume
      - label: "Workouts"
        field: workout_count
      - label: "PRs"
        field: pr_count
```

---

## Default Exercise Library

```yaml
exercises:
  # Chest
  - id: bench-press
    name: Bench Press
    category: chest
  - id: incline-bench-press
    name: Incline Bench Press
    category: chest
  - id: dumbbell-fly
    name: Dumbbell Fly
    category: chest
    
  # Back
  - id: deadlift
    name: Deadlift
    category: back
  - id: barbell-row
    name: Barbell Row
    category: back
  - id: pull-up
    name: Pull-up
    category: back
  - id: lat-pulldown
    name: Lat Pulldown
    category: back
    
  # Shoulders
  - id: overhead-press
    name: Overhead Press
    category: shoulders
  - id: lateral-raise
    name: Lateral Raise
    category: shoulders
  - id: face-pull
    name: Face Pull
    category: shoulders
    
  # Arms
  - id: barbell-curl
    name: Barbell Curl
    category: arms
  - id: tricep-pushdown
    name: Tricep Pushdown
    category: arms
  - id: hammer-curl
    name: Hammer Curl
    category: arms
    
  # Legs
  - id: squat
    name: Squat
    category: legs
  - id: leg-press
    name: Leg Press
    category: legs
  - id: romanian-deadlift
    name: Romanian Deadlift
    category: legs
  - id: leg-curl
    name: Leg Curl
    category: legs
  - id: leg-extension
    name: Leg Extension
    category: legs
  - id: calf-raise
    name: Calf Raise
    category: legs
    
  # Core
  - id: plank
    name: Plank
    category: core
```

---

## Implementation Phases

### Phase 1: Foundation (MVP)
**Goal:** Working event-sourced backend with manual UI input

- [ ] SQLite database setup with event store
- [ ] Event validation and storage
- [ ] Basic projections (current_workout, workout_history, templates)
- [ ] FastAPI endpoints for events and projections
- [ ] Simple HTML/Tailwind UI for workout logging
- [ ] Manual input (no voice yet)
- [ ] Template support: save template, start from template
- [ ] Template management UI (list, delete)
- [ ] Interactive tutorial (mock workout walkthrough)

**Ship Criteria:** Can complete tutorial, complete a real workout via UI, save as template, start new workout from template, see history

### Phase 2: Voice + LLM
**Goal:** Hands-free logging via voice

- [ ] Web Speech API integration
- [ ] LLM integration with emit/query tools
- [ ] Schema-aware system prompt
- [ ] Voice button in UI
- [ ] Confirmation flow for voice input

**Ship Criteria:** Can log a set by speaking "Bench 100 for 8"

### Phase 3: Smart Features
**Goal:** Context-aware assistance

- [ ] "Same as last time" support
- [ ] Personal record detection
- [ ] Previous values display
- [ ] Exercise search/fuzzy matching

**Ship Criteria:** LLM understands "same weight, 2 more reps"

### Phase 4: Aggregates + Analytics
**Goal:** Progress visualization

- [ ] Time-based aggregate calculations
- [ ] Daily/weekly/monthly/yearly stats
- [ ] Progress charts (volume, strength)
- [ ] Stats API endpoints

**Ship Criteria:** Can see volume trend over 12 weeks

### Phase 5: Export + Polish
**Goal:** Data ownership and UX polish

- [ ] CSV export (all data)
- [ ] Event log export
- [ ] PWA support
- [ ] Offline capability
- [ ] Theme toggle

**Ship Criteria:** Can export all data and install as app

---

## File Structure

```
/gym_app/
├── app_specification.md          # Product specification
├── technical_specification.md    # This document
├── schema/
│   ├── events.yaml               # Event definitions
│   ├── entities.yaml             # Entity definitions
│   └── aggregates.yaml           # Aggregate definitions
├── backend/
│   ├── main.py                   # FastAPI app
│   ├── database.py               # SQLite operations
│   ├── events.py                 # Event handling
│   ├── projections.py            # Projection logic
│   ├── aggregates.py             # Aggregate calculations
│   ├── llm.py                    # LLM integration
│   └── api/
│       ├── events.py
│       ├── projections.py
│       ├── stats.py
│       └── voice.py
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── data/
│   └── exercises.yaml            # Default exercise library
└── workspace/
    └── {user_id}/
        └── gym.db                # User's database
```

---

## Browser Compatibility

| Feature | Chrome | Safari | Firefox | Edge |
|---------|--------|--------|---------|------|
| Web Speech API | ✅ | ✅ (webkit) | ❌ | ✅ |
| SQLite (via backend) | ✅ | ✅ | ✅ | ✅ |
| Fetch API | ✅ | ✅ | ✅ | ✅ |
| Service Worker | ✅ | ✅ | ✅ | ✅ |

**Note:** Firefox users will use manual input only (no voice).

---

## Testing Strategy

### Unit Tests

| Component | What to Test |
|-----------|--------------|
| **Event Validation** | Schema enforcement, required fields, type coercion, enum values |
| **Projection Logic** | State updates for each event type, edge cases (empty workout, duplicate sets) |
| **Aggregate Calculations** | Volume math, PR detection, period boundaries (week start, month rollover) |
| **LLM Tool Responses** | Mock LLM responses, validate emit payloads, error handling |

### Integration Tests

| Flow | Test Case |
|------|-----------|
| **Complete Workout** | Start → Add exercises → Log sets → Finish → Verify in history |
| **Event Replay** | Delete projections → Rebuild from events → Verify state matches |
| **Voice → Event** | Mock STT transcript → LLM processing → Validate emitted event |

### Replay Tests (Event Sourcing Specific)

```python
def test_projection_rebuild():
    """Projections can be rebuilt from events at any time."""
    # 1. Run a series of events
    events = [
        ("WorkoutStarted", {...}),
        ("SetLogged", {...}),
        ("WorkoutCompleted", {...}),
    ]
    for event_type, payload in events:
        emit(event_type, payload)
    
    # 2. Capture current projection state
    original_state = get_projection("workout_history")
    
    # 3. Delete all projections
    clear_projections()
    
    # 4. Rebuild from events
    rebuild_all_projections()
    
    # 5. Verify state matches
    rebuilt_state = get_projection("workout_history")
    assert original_state == rebuilt_state
```

### LLM Contract Tests

```python
def test_llm_emit_validation():
    """LLM-generated events must pass schema validation."""
    # Mock LLM response
    llm_response = {
        "tool": "emit",
        "args": {
            "event_type": "SetLogged",
            "payload": {"exercise_id": "bench-press", "weight": 100, "reps": 8}
        }
    }
    
    # Should not raise validation error
    result = process_llm_tool_call(llm_response)
    assert result["success"] == True
```

---

## Operations

### Projection Rebuild

Projections are derived views and can be rebuilt from the event log at any time. This is useful for:
- Fixing bugs in projection logic
- Adding new projections retroactively
- Disaster recovery

#### CLI Command

```bash
# Rebuild all projections for a user
python -m backend.cli rebuild-projections --user-id default

# Rebuild specific projection
python -m backend.cli rebuild-projections --user-id default --projection current_workout

# Rebuild all aggregates
python -m backend.cli rebuild-aggregates --user-id default
```

#### Admin API Endpoint (Optional)

```
POST /api/admin/rebuild-projections
POST /api/admin/rebuild-aggregates
```

These endpoints should be protected (not exposed in production without auth).

### Database Migrations

SQLite schema changes are managed via versioned migration scripts.

#### Migration Strategy

```
/migrations/
├── 001_initial_schema.sql
├── 002_add_exercise_category.sql
└── 003_add_aggregate_indexes.sql
```

#### Event Schema Versioning

Events include a `schema_version` field for forward compatibility:

```sql
-- Events table includes version
CREATE TABLE events (
    ...
    schema_version INTEGER DEFAULT 1
);
```

When processing old events during replay:
```python
def process_event(event):
    if event.schema_version == 1:
        # Handle v1 schema (maybe missing fields)
        payload = migrate_v1_to_current(event.payload)
    else:
        payload = event.payload
    
    apply_to_projection(payload)
```

### Backup & Restore

```bash
# Backup: just copy the SQLite file
cp /workspace/{user_id}/gym.db /backups/gym_$(date +%Y%m%d).db

# Restore: copy it back
cp /backups/gym_20251206.db /workspace/{user_id}/gym.db
```

---

## LLM Performance Considerations

### Latency Budget

| Step | Target | Notes |
|------|--------|-------|
| Speech-to-Text | ~500ms | Browser-dependent, network required |
| LLM Processing | ~500ms | GPT-4o-mini / Claude Haiku |
| Event Storage | ~10ms | SQLite is fast |
| Projection Update | ~10ms | In-memory, then persist |
| **Total** | **~1 second** | Acceptable for gym use |

### Caching

```python
# Cache exercise search results (frequently queried)
@lru_cache(maxsize=100)
def search_exercises(query: str) -> list[Exercise]:
    return db.search_exercises(query)

# Cache invalidated when custom exercises added
def add_custom_exercise(exercise: Exercise):
    db.insert_exercise(exercise)
    search_exercises.cache_clear()
```

### Rate Limiting

```python
# Per-user rate limit for LLM calls
RATE_LIMIT = 30  # requests per minute

@app.post("/api/voice/process")
@rate_limit(RATE_LIMIT, per="minute", key="user_id")
async def process_voice(transcript: str, user_id: str):
    ...
```

### Fallback When LLM Unavailable

```python
async def process_voice(transcript: str):
    try:
        result = await call_llm_with_timeout(transcript, timeout=5.0)
        return result
    except (LLMTimeoutError, LLMUnavailableError):
        # Fallback: return transcript for manual parsing in UI
        return {
            "status": "fallback",
            "message": "Voice processing unavailable. Please enter manually.",
            "transcript": transcript
        }
```

The UI should handle this gracefully:
- Show the transcript
- Pre-fill input fields with detected numbers
- Let user confirm/edit manually

### Fallback for Poor Speech Recognition

When STT produces inaccurate transcripts, the UI provides quick-fix controls:

```
┌─────────────────────────────────────────────────────────────────┐
│  🎤 Heard: "bench press 100 kilos for fate"                     │
│                                          ~~~~                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Exercise: [Bench Press     ▼]                               ││
│  │ Weight:   [100      ] kg                                    ││
│  │ Reps:     [8        ] ← Quick fix: tap to change "fate"→8  ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│  [✓ Confirm]  [🎤 Try Again]  [✕ Cancel]                        │
└─────────────────────────────────────────────────────────────────┘
```

**Quick-fix behaviors:**
- Tap on a misheard word → keyboard opens for that field
- Number detection: extract digits from transcript as hints
- Exercise fuzzy match: suggest closest exercise names
- One-tap confirm if everything looks right

### Cost Optimization

| Strategy | Savings |
|----------|---------|
| Use GPT-4o-mini instead of GPT-4 | ~20x cheaper |
| Cache common queries (exercise search) | Reduces calls |
| Batch context (send workout state once, not per set) | Fewer tokens |
| Short system prompts | Fewer input tokens |
| Token cap per request | Prevents runaway costs |

**Token Limits:**

```python
LLM_CONFIG = {
    "max_input_tokens": 500,   # Context + transcript
    "max_output_tokens": 200,  # Response + tool calls
}

# Truncate context if needed
def prepare_context(workout, transcript):
    context = build_context(workout)
    if count_tokens(context) > LLM_CONFIG["max_input_tokens"] - 100:
        # Summarize workout instead of full detail
        context = summarize_workout(workout)
    return context
```

**Estimated cost:** ~$0.0001 per voice command (at GPT-4o-mini rates)

---

## Data-Driven UI: Schema Integration

### How Schema Updates Flow to UI

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Schema Change  │ ──▶ │  Backend        │ ──▶ │  UI             │
│  (events.yaml)  │     │  Validation     │     │  Form Generation│
└─────────────────┘     └─────────────────┘     └─────────────────┘

Example: Adding RPE (Rate of Perceived Exertion) field

1. Update schema/events.yaml:
   SetLogged:
     payload:
       ...
       rpe:                           # ← New field
         type: integer
         min: 1
         max: 10
         optional: true

2. Backend automatically:
   - Validates rpe if present
   - Stores in event payload
   - LLM learns about it (schema in prompt)

3. UI automatically:
   - Reads schema via GET /api/schema
   - Generates input field for 'rpe'
   - Shows 1-10 slider/dropdown
```

### Frontend Schema Consumption

```javascript
// Fetch schema on app load
const schema = await fetch('/api/schema/events').then(r => r.json());

// Generate form fields dynamically
function renderSetForm(exerciseId) {
  const setSchema = schema.events.SetLogged.payload;
  
  return Object.entries(setSchema).map(([field, spec]) => {
    if (spec.auto) return null;  // Skip auto-generated fields
    
    switch (spec.type) {
      case 'number':
        return <NumberInput 
          name={field} 
          min={spec.min} 
          max={spec.max}
          required={!spec.optional}
        />;
      case 'integer':
        if (spec.enum) {
          return <Select name={field} options={spec.enum} />;
        }
        return <IntegerInput name={field} min={spec.min} max={spec.max} />;
      // ... handle other types
    }
  });
}
```

### View Configuration Reload

When view configs change, the UI can hot-reload:

```javascript
// Poll for config changes (or use WebSocket)
async function checkForUpdates() {
  const config = await fetch('/api/views/current_workout').then(r => r.json());
  if (config.version !== currentVersion) {
    reloadView(config);
  }
}
```

This enables:
- Adding new fields without frontend deployment
- A/B testing different layouts
- User-customizable views (future)

---

## Interactive Tutorial System

The tutorial provides a guided mock workout experience for new users to learn voice commands and UI interactions without affecting real data.

### Tutorial Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      TUTORIAL MODE                              │
│                                                                 │
│   ┌─────────────────┐    ┌─────────────────────────────────┐   │
│   │  Tutorial State │    │  Sandbox Environment            │   │
│   │  Machine        │    │                                 │   │
│   │                 │    │  • Mock current_workout         │   │
│   │  step: 3        │    │  • Mock exercise_history        │   │
│   │  completed: [1,2]│   │  • Mock templates               │   │
│   │  skipped: false │    │  • Events NOT persisted         │   │
│   └────────┬────────┘    └─────────────────────────────────┘   │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Tutorial UI Overlay                                    │  │
│   │                                                         │  │
│   │  ┌─────────────────────────────────────────────────┐   │  │
│   │  │ Step 3 of 9                                     │   │  │
│   │  │                                                 │   │  │
│   │  │ "Now let's add your first exercise..."         │   │  │
│   │  │                                                 │   │  │
│   │  │ 🎤 Try saying: "Bench press 60 kilos for 10"   │   │  │
│   │  │                                                 │   │  │
│   │  │ [Skip Step] [Exit Tutorial]                    │   │  │
│   │  └─────────────────────────────────────────────────┘   │  │
│   └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Tutorial State

```yaml
# Stored in localStorage (not database)
tutorial_state:
  started: boolean
  completed: boolean
  current_step: integer
  completed_steps: [integer]
  skipped: boolean
  
# Tutorial steps definition
tutorial_steps:
  - id: 1
    name: "welcome"
    type: "info"
    
  - id: 2
    name: "start_workout"
    type: "action"
    expected_event: "WorkoutStarted"
    voice_prompt: "Start a workout"
    ui_alternative: "Tap 'Start Workout' button"
    
  - id: 3
    name: "log_first_set"
    type: "action"
    expected_event: "SetLogged"
    voice_prompt: "Bench press 60 kilos for 10"
    validation:
      exercise_id: "bench-press"
      
  - id: 4
    name: "quick_set"
    type: "action"
    expected_event: "SetLogged"
    voice_prompt: "60 for 8"
    hint: "You don't need to repeat the exercise name"
    
  - id: 5
    name: "ui_add_exercise"
    type: "ui_action"
    target: "add_exercise_button"
    
  - id: 6
    name: "same_as_last_time"
    type: "action"
    expected_event: "SetLogged"
    voice_prompt: "Same as last time"
    mock_history:
      squat: { weight: 80, reps: 5, unit: "kg" }
      
  - id: 7
    name: "save_template"
    type: "action"
    expected_event: "TemplateCreated"
    voice_prompt: "Save this as push day"
    
  - id: 8
    name: "finish_workout"
    type: "action"
    expected_event: "WorkoutCompleted"
    voice_prompt: "I'm done"
    
  - id: 9
    name: "summary"
    type: "info"
```

### Sandbox Mode

During tutorial, all operations happen in a sandbox:

```python
class TutorialSandbox:
    """In-memory sandbox that mimics real data operations."""
    
    def __init__(self):
        self.mock_workout = None
        self.mock_events = []
        self.mock_history = {
            "bench-press": [{"weight": 60, "reps": 8, "unit": "kg"}],
            "squat": [{"weight": 80, "reps": 5, "unit": "kg"}],
        }
        self.mock_templates = []
    
    def emit(self, event_type: str, payload: dict):
        """Process event without persisting to real database."""
        event = {"type": event_type, "payload": payload}
        self.mock_events.append(event)
        
        if event_type == "WorkoutStarted":
            self.mock_workout = {"exercises": [], "focus": None}
        elif event_type == "SetLogged":
            # Update mock workout state
            pass
        # ... handle other events
        
        return {"success": True, "sandbox": True}
    
    def query(self, projection: str):
        """Return mock data for queries."""
        if projection == "exercise_history":
            return self.mock_history
        # ... handle other queries
```

### Tutorial API

```python
@app.get("/api/tutorial/state")
async def get_tutorial_state():
    """Get current tutorial progress (from localStorage via client)."""
    pass

@app.post("/api/tutorial/start")
async def start_tutorial():
    """Initialize tutorial sandbox."""
    return {"sandbox_id": uuid4(), "step": 1}

@app.post("/api/tutorial/action")
async def tutorial_action(step: int, event_type: str, payload: dict):
    """
    Process action in sandbox, validate against expected step.
    Returns success + next step prompt.
    """
    expected = TUTORIAL_STEPS[step]
    
    if event_type != expected["expected_event"]:
        return {"success": False, "hint": expected["voice_prompt"]}
    
    # Process in sandbox
    sandbox.emit(event_type, payload)
    
    return {
        "success": True,
        "next_step": step + 1,
        "message": expected.get("success_message", "Great!")
    }

@app.post("/api/tutorial/complete")
async def complete_tutorial():
    """Mark tutorial as completed, clean up sandbox."""
    pass
```

### Tutorial UI Component

```javascript
// Tutorial overlay component (Alpine.js)
function tutorialController() {
    return {
        active: false,
        step: 1,
        steps: [], // Loaded from API
        
        async start() {
            this.active = true;
            const res = await fetch('/api/tutorial/start', {method: 'POST'});
            this.steps = await res.json();
        },
        
        async handleAction(eventType, payload) {
            const res = await fetch('/api/tutorial/action', {
                method: 'POST',
                body: JSON.stringify({step: this.step, event_type: eventType, payload})
            });
            const result = await res.json();
            
            if (result.success) {
                this.step = result.next_step;
                this.showSuccess(result.message);
            } else {
                this.showHint(result.hint);
            }
        },
        
        skip() {
            this.step++;
        },
        
        exit() {
            this.active = false;
            // Offer to start real workout
        }
    }
}
```

### Tutorial Triggers

| Trigger | Behavior |
|---------|----------|
| First app launch | Show welcome screen with "Take Tutorial" option |
| First "Start Workout" tap | Prompt: "Want to try a practice workout first?" |
| Help menu | "Tutorial" option always available |
| 30s inactivity on first workout | Gentle prompt: "Need help? Try the tutorial" |

---

## Operational Modes

The system operates in distinct modes that affect data persistence and behavior:

| Mode | Events Persisted | Projections Updated | Use Case |
|------|------------------|---------------------|----------|
| `normal` | ✅ Yes | ✅ Yes | Regular workout logging |
| `tutorial_sandbox` | ❌ No (in-memory) | ❌ No (mock data) | New user onboarding |
| `diagnostic` | ❌ No | Depends | Replay, rebuild, debugging |

### Mode Detection

```python
class OperationalMode(Enum):
    NORMAL = "normal"
    TUTORIAL_SANDBOX = "tutorial_sandbox"
    DIAGNOSTIC = "diagnostic"

def get_current_mode(request: Request) -> OperationalMode:
    if request.headers.get("X-Tutorial-Mode") == "true":
        return OperationalMode.TUTORIAL_SANDBOX
    if request.headers.get("X-Diagnostic-Mode") == "true":
        return OperationalMode.DIAGNOSTIC
    return OperationalMode.NORMAL

def emit_event(event: Event, mode: OperationalMode):
    if mode == OperationalMode.NORMAL:
        db.append_event(event)          # Persist to SQLite
        update_projections(event)        # Update real projections
    elif mode == OperationalMode.TUTORIAL_SANDBOX:
        sandbox.process(event)           # In-memory only
    elif mode == OperationalMode.DIAGNOSTIC:
        log.info(f"Diagnostic: {event}") # Log but don't persist
```

### Diagnostic Mode Use Cases

- **Event replay:** Rebuild projections from event log
- **Schema migration testing:** Test new event versions without committing
- **Debugging:** Trace event flow without side effects

---

## Security Considerations

### MVP (Single User)
- Hardcoded user ID
- No authentication
- Local SQLite file

### Future (Multi-User)
- Token-based authentication
- User ID in JWT
- Scoped database access
- Rate limiting on LLM calls

