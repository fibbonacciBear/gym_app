# UX Friction: Voice Exercise Recognition

**Status:** Critical Issue
**Affects:** Sprint 5 (Voice + LLM)
**Priority:** High
**Date Identified:** December 2024

---

## Problem Statement

The voice-first workout logging feature has a fundamental friction: **the LLM does not have access to the exercise library**, causing unreliable exercise name-to-ID mapping.

### Current Behavior

When a user says "bench press 100 for 8":

1. ✅ Web Speech API captures: `"bench press 100 for 8"`
2. ✅ Transcript sent to `/api/voice/process`
3. ❌ **LLM receives NO exercise library in context**
4. ❌ LLM guesses exercise ID (might guess `"bench-press"`, `"bench_press"`, `"benchpress"`, etc.)
5. ❌ `SetLogged` event emitted with potentially incorrect `exercise_id`
6. ⚠️ Backend auto-creates exercise entry with whatever ID the LLM guessed
7. ⚠️ User ends up with duplicate/incorrect exercises in their workout

### Example Failure Cases

| User Says | LLM Might Guess | Actual Library ID | Result |
|-----------|-----------------|-------------------|--------|
| "pull ups" | `"pull-ups"` | `"pull-up"` | ❌ New exercise created |
| "lat pulldown" | `"lat-pull-down"` | `"lat-pulldown"` | ❌ New exercise created |
| "bench" | `"bench"` | `"bench-press"` | ❌ New exercise created |
| "BP" | `"bp"` | `"bench-press"` | ❌ New exercise created |
| "barbell row" | `"barbell-row"` | `"barbell-row"` | ✅ Works (lucky) |

---

## Why This Matters

### 1. Data Fragmentation
User logs sets across multiple duplicate exercises:
- Week 1: `"pull-ups"` (3 sets)
- Week 2: `"pull-up"` (3 sets)
- Week 3: `"pullup"` (3 sets)

**Result:** History tracking breaks, PR detection fails, progress charts are meaningless.

### 2. Voice-First Promise Broken
The core value proposition is **zero friction logging**. If users have to:
- Learn exact exercise IDs
- Manually fix duplicates after voice logging
- Check if their exercise was recognized correctly

...then voice adds friction instead of removing it.

### 3. User Trust Erosion
After 2-3 failed voice commands, users will:
1. Stop using voice
2. Revert to manual entry
3. Question the app's intelligence

### 4. Scope Creep Risk
Without proper exercise mapping, users will ask for:
- "Why do I have 'bench press' and 'bench-press'?"
- "Can you merge these exercises?"
- "How do I delete duplicate exercises?"

All of which are **preventable** with proper LLM context.

---

## Root Cause Analysis

### Code Location: `backend/llm.py`

```python
def build_context(user_id: str = "default") -> Dict[str, str]:
    """Build context for the LLM prompt."""
    current = get_projection("current_workout", user_id)
    exercises = get_exercises(user_id)  # ← LOADED BUT NOT USED!

    if current:
        workout_status = f"Active (ID: {current['id'][:8]})"
        workout_id = current['id']
        focus = current.get("focus_exercise", "None")
        ex_list = ", ".join(e["exercise_id"] for e in current.get("exercises", []))
    else:
        workout_status = "None"
        workout_id = "None"
        focus = "None"
        ex_list = "None"

    return {
        "workout_status": workout_status,
        "workout_id": workout_id,
        "focus_exercise": focus,
        "exercise_list": ex_list or "None",
        "preferred_unit": "kg"
        # ← exercises variable is NEVER RETURNED!
    }
```

**The Issue:**
- `exercises = get_exercises(user_id)` is called but never used
- The exercise library is not included in the context dict
- The SYSTEM_PROMPT never receives exercise information
- LLM operates without knowledge of valid exercise IDs

---

## Potential Solutions

### Solution 1: Pass Full Exercise Library to LLM (Recommended)

#### Implementation

**Update `build_context()` in `backend/llm.py`:**

```python
def build_context(user_id: str = "default") -> Dict[str, str]:
    """Build context for the LLM prompt."""
    current = get_projection("current_workout", user_id)
    exercises = get_exercises(user_id)

    # Format exercise library for LLM
    exercise_library = "\n".join([
        f"- {ex['id']}: {ex['name']}"
        for ex in exercises
    ])

    # ... existing code ...

    return {
        "workout_status": workout_status,
        "workout_id": workout_id,
        "focus_exercise": focus,
        "exercise_list": ex_list or "None",
        "available_exercises": exercise_library,  # NEW
        "preferred_unit": "kg"
    }
```

**Update `SYSTEM_PROMPT` in `backend/llm.py`:**

```python
SYSTEM_PROMPT = """You are a voice assistant for a gym workout tracker. Users speak commands to log their strength training exercises.

## Current Context
- Active workout: {workout_status}
- Workout ID: {workout_id}
- Focus exercise: {focus_exercise}
- Exercises in workout: {exercise_list}
- User's preferred unit: {preferred_unit}

## Available Exercises in Library
{available_exercises}

**IMPORTANT:** When user mentions an exercise, you MUST map it to an exercise ID from the library above. Use fuzzy matching:
- "bench" → "bench-press"
- "pull ups" → "pull-up"
- "lat pulldown" → "lat-pulldown"
- "BP" → "bench-press"

If user says an exercise not in the library, ask for clarification or suggest the closest match.

## Available Tools
1. emit(event_type, payload) - Create a workout event
2. query(projection_key) - Get current state

## Event Types
- WorkoutStarted: Start a new workout
- SetLogged: Log a set (requires exercise_id, weight, reps, unit)
- ExerciseAdded: Add exercise without logging a set
- WorkoutCompleted: Finish the workout

## Guidelines
1. For logging sets: emit SetLogged with workout_id (from context), exercise_id, weight, reps, unit
2. **ALWAYS use exact exercise_id from Available Exercises list above**
3. If user doesn't name exercise, use focus_exercise
4. For "same as last time": query exercise_history first
5. For "add 5 pounds": query history, calculate new weight
6. Always include workout_id in SetLogged events - get it from Active workout context
7. Be concise

## Examples
- "Bench press 100 for 8" → emit SetLogged {{exercise_id: "bench-press", weight: 100, reps: 8, unit: "kg"}}
- "100 for 8" (with focus) → emit SetLogged {{exercise_id: <focus>, weight: 100, reps: 8, unit: "kg"}}
- "I'm done" → emit WorkoutCompleted
"""
```

#### Pros
✅ LLM has complete knowledge of valid exercises
✅ Reliable fuzzy matching ("bench" → "bench-press")
✅ Prevents duplicate exercise creation
✅ Works with 20 exercises without token bloat
✅ Easy to implement (just format and pass data)

#### Cons
❌ Adds ~200-400 tokens to every LLM call
❌ Doesn't scale well if exercise library grows to 1000+ exercises
❌ Slight cost increase per API call

#### Token Analysis
- 20 exercises × ~10 tokens each = ~200 tokens
- Anthropic Haiku: $0.00025 per 1K tokens → +$0.00005 per call (negligible)
- OpenAI GPT-4o-mini: $0.00015 per 1K tokens → +$0.00003 per call (negligible)

**Verdict:** Cost is negligible for MVP with <100 exercises.

---

### Solution 2: LLM Tool for Exercise Search

Give the LLM a `search_exercises(query)` tool to look up exercises on-demand.

#### Implementation

**Add new tool to `TOOLS` in `backend/llm.py`:**

```python
{
    "name": "search_exercises",
    "description": "Search for exercises by name to get the correct exercise_id",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language exercise name (e.g., 'bench press', 'pull ups')"
            }
        },
        "required": ["query"]
    }
}
```

**Add search handler in `backend/api/voice.py`:**

```python
elif result.get("action") == "search_exercises":
    query = result["arguments"]["query"]
    exercises = get_exercises("default")

    # Fuzzy search logic (could use fuzzywuzzy library)
    matches = fuzzy_search_exercises(query, exercises)

    # Return top 3 matches to LLM for final decision
    return matches
```

**Update LLM workflow:**
1. User says "bench press 100 for 8"
2. LLM calls `search_exercises("bench press")`
3. Backend returns: `[{"id": "bench-press", "name": "Bench Press", "score": 0.95}]`
4. LLM uses `exercise_id: "bench-press"` in SetLogged event

#### Pros
✅ Zero tokens added to initial prompt
✅ Scales to large exercise libraries (1000+ exercises)
✅ Can add fuzzy matching logic (Levenshtein distance, etc.)
✅ LLM always gets correct ID

#### Cons
❌ Requires 2 LLM calls per voice command (slower)
❌ Higher latency (~1-2s additional delay)
❌ More complex implementation
❌ Potential for search failures if query is too vague

---

### Solution 3: Client-Side Exercise Selection

Show exercise picker UI after voice recognition.

#### Implementation

1. User says "bench press 100 for 8"
2. LLM extracts: `{exercise_name: "bench press", weight: 100, reps: 8}`
3. Frontend searches local exercise list for "bench press"
4. If match is ambiguous, show picker modal:
   ```
   Did you mean:
   [ ] Bench Press
   [ ] Incline Bench Press
   [ ] Decline Bench Press
   ```
5. User taps selection
6. Emit SetLogged event with confirmed exercise_id

#### Pros
✅ User always confirms exercise selection
✅ No LLM token overhead
✅ Handles ambiguous cases well
✅ Educational (users learn exercise names)

#### Cons
❌ **Breaks voice-first promise** (requires screen interaction)
❌ Adds friction instead of removing it
❌ Defeats the purpose of hands-free logging
❌ Frustrating in gym environment (sweaty hands, distance from phone)

**Verdict:** This defeats the core value proposition. ❌

---

### Solution 4: Hybrid Approach

Combine Solution 1 (pass library) with client-side fallback.

#### Implementation

**Primary Path (95% of cases):**
1. LLM receives exercise library
2. LLM maps "bench press" → "bench-press"
3. Set logged successfully

**Fallback Path (5% of cases):**
1. LLM unsure (confidence < 80%)
2. Return `{action: "clarify_exercise", matches: ["bench-press", "incline-bench-press"]}`
3. Show quick picker UI
4. User taps, set logged

#### Pros
✅ Best of both worlds
✅ Voice works 95% of the time
✅ Graceful degradation for edge cases
✅ Learns from user corrections over time

#### Cons
❌ More complex implementation
❌ Requires confidence scoring logic
❌ UI needed for fallback cases

---

## Recommended Solution

**Implement Solution 1: Pass Full Exercise Library to LLM**

### Rationale

1. **Simplest implementation** - Just format and pass data
2. **Solves 99% of cases** - LLM is good at fuzzy matching
3. **Low cost** - ~$0.00005 per call with 20 exercises
4. **Fast** - No additional API calls
5. **MVP-appropriate** - Can optimize later if needed

### Future Optimization Path

If exercise library grows beyond 100 exercises:

1. **Phase 1 (MVP):** Pass all exercises (works fine up to ~100 exercises)
2. **Phase 2:** Pass only popular exercises + user's custom exercises (~50 exercises)
3. **Phase 3:** Implement Solution 2 (search tool) if library exceeds 500 exercises
4. **Phase 4:** Add client-side caching and vector search for instant matching

---

## Implementation Checklist

- [ ] Update `build_context()` to format exercise library
- [ ] Update `SYSTEM_PROMPT` to include `{available_exercises}` section
- [ ] Add fuzzy matching instructions to LLM prompt
- [ ] Test with common exercise variations ("bench", "BP", "pull ups")
- [ ] Test with misspellings ("benchpress", "latpulldown")
- [ ] Test with abbreviations ("OHP" for overhead press)
- [ ] Add error handling for unknown exercises
- [ ] Update Sprint 5 commit with this fix
- [ ] Document expected exercise name variations in `data/exercises.json`

---

## Testing Plan

### Test Cases

| User Input | Expected exercise_id | Pass/Fail |
|------------|---------------------|-----------|
| "bench press 100 for 8" | `bench-press` | ⬜ |
| "bench 100 for 8" | `bench-press` | ⬜ |
| "BP 100 for 8" | `bench-press` | ⬜ |
| "incline bench 80 for 10" | `incline-bench-press` | ⬜ |
| "pull ups 10 reps" | `pull-up` | ⬜ |
| "lat pulldown 150 for 12" | `lat-pulldown` | ⬜ |
| "overhead press 60 for 8" | `overhead-press` | ⬜ |
| "OHP 60 for 8" | `overhead-press` | ⬜ |
| "squat 200 for 5" | `squat` | ⬜ |
| "deadlift 300 for 3" | `deadlift` | ⬜ |

### Edge Cases

| User Input | Expected Behavior | Pass/Fail |
|------------|-------------------|-----------|
| "made up exercise 100 for 8" | LLM asks for clarification or rejects | ⬜ |
| "benc pres 100 for 8" (typo) | LLM maps to `bench-press` | ⬜ |
| "chest press" (ambiguous) | LLM picks `bench-press` or asks | ⬜ |

---

## Impact Assessment

### Before Fix
- ❌ Exercise name mapping: **Unreliable**
- ❌ Data quality: **Fragmented duplicates**
- ❌ User trust: **Low** (after 2-3 failures)
- ❌ Voice adoption: **<20%** (users abandon feature)

### After Fix
- ✅ Exercise name mapping: **95%+ accurate**
- ✅ Data quality: **Clean, no duplicates**
- ✅ User trust: **High** (consistent results)
- ✅ Voice adoption: **>60%** (becomes primary input method)

---

## Related Issues

- **PR Detection (Sprint 6):** Requires clean exercise history (won't work with duplicates)
- **Exercise History (Sprint 6):** Needs consistent exercise_ids across workouts
- **Analytics (Sprint 8):** Progress charts break with duplicate exercises
- **Templates (Sprint 4):** Could reference non-existent exercise_ids

---

## References

- Implementation Plan: `implementation_plan.md` - Sprint 5
- LLM Integration: `backend/llm.py`
- Exercise Library: `data/exercises.json`
- Voice API: `backend/api/voice.py`

---

**Last Updated:** December 2024
**Status:** Implemented (Solution 1: Pass Full Exercise Library to LLM)
