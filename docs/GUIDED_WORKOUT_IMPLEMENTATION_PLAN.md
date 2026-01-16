# Guided Workout Implementation Plan

## Problem Statement

Currently, when a user starts a workout from a template, they only see the list of exercises with 0 sets logged. They cannot see:
- How many sets they're supposed to do
- What reps they should aim for at each weight
- A way to track completion as they progress through the workout

This plan adds a **"Guided Workout Mode"** where users can see and follow their template's prescribed sets, reps, and weights.

## Current State

### What Templates Store
Templates already contain the following data per exercise (see `backend/api/templates.py`):
- `exercise_id`: The exercise identifier
- `target_sets`: Number of sets to perform (e.g., 3)
- `target_reps`: Number of reps per set (e.g., 10)
- `target_weight`: Target weight (e.g., 100.0)
- `target_unit`: Weight unit (kg or lb)
- `set_type`: Type of set (standard, warmup, dropset, etc.)
- `rest_seconds`: Rest time between sets (default 60)

### Current Workflow When Starting from Template
1. User clicks "Today's Workout" button
2. User selects a template from the modal
3. `startFromTemplate(templateId)` is called
4. Backend endpoint `/api/templates/{template_id}/start` is called
5. Backend emits `WorkoutStarted` event with `exercise_ids` only (line 214 in `backend/api/templates.py`)
6. Current workout projection is created with exercises showing 0 sets
7. User manually logs each set using the UI or voice

**The Problem**: The template's `target_sets`, `target_reps`, and `target_weight` data is **not** passed to the workout, so the user has no guidance.

## Desired User Experience

### Visual Design
When a workout is started from a template, each exercise should display:

```
🏋️ Bench Press
Target: 3 sets × 10 reps @ 100kg

Set 1: [ ] 100kg × 10 reps
Set 2: [ ] 100kg × 10 reps  
Set 3: [ ] 100kg × 10 reps

+ Add Set (in case user wants to do more)
```

### User Interactions
1. **Checkbox to complete a set**: User taps the checkbox when they complete a set
   - The checkbox should transform into a "✓ LOGGED" indicator
   - The set should actually be logged to the system (emit SetLogged event)
   
2. **Edit before logging**: User can tap the set row to edit weight/reps before checking it off
   - Opens a modal to adjust the values
   - Then logs the modified set

3. **Add extra sets**: User can add more sets beyond the template's target_sets
   - Use existing "+ Set" button functionality

4. **Mixed mode support**: Some exercises might have targets, others might not (free-form)
   - If an exercise has targets, show guided mode
   - If no targets, show standard mode (current behavior)

## Implementation Steps

### Step 1: Update Backend - Pass Template Details to Workout

**File**: `backend/api/templates.py`

**Current code (lines 208-217)**:
```python
result, derived = emit_event(
    EventType.WORKOUT_STARTED,
    {
        "name": template["name"],
        "from_template_id": template_id,
        "exercise_ids": template["exercise_ids"]
    },
    user_id
)
```

**Change to**:
```python
# Extract full exercise details from template (if using new format)
exercise_plans = []
if template.get("exercises"):
    # New format: full exercise specs with targets
    exercise_plans = template["exercises"]
else:
    # Legacy format: just IDs (no targets)
    exercise_plans = [{"exercise_id": ex_id} for ex_id in template.get("exercise_ids", [])]

result, derived = emit_event(
    EventType.WORKOUT_STARTED,
    {
        "name": template["name"],
        "from_template_id": template_id,
        "exercise_ids": [ex.get("exercise_id") for ex in exercise_plans],
        "exercise_plans": exercise_plans  # NEW: Pass full plan details
    },
    user_id
)
```

### Step 2: Update Projection Handler - Store Template Targets

**File**: `backend/events.py`

**Current code (lines 243-264)**:
```python
if event_type == EventType.WORKOUT_STARTED:
    workout_id = payload.get("workout_id")
    current_workout = {
        "id": workout_id,
        "started_at": timestamp,
        "from_template_id": payload.get("from_template_id"),
        "focus_exercise": None,
        "exercises": []
    }

    exercise_ids = payload.get("exercise_ids") or []
    for ex_id in exercise_ids:
        current_workout["exercises"].append({
            "exercise_id": ex_id,
            "sets": []
        })
```

**Change to**:
```python
if event_type == EventType.WORKOUT_STARTED:
    workout_id = payload.get("workout_id")
    current_workout = {
        "id": workout_id,
        "started_at": timestamp,
        "from_template_id": payload.get("from_template_id"),
        "focus_exercise": None,
        "exercises": []
    }

    # Support both legacy (exercise_ids) and new (exercise_plans) formats
    exercise_plans = payload.get("exercise_plans") or []
    if not exercise_plans:
        # Fallback to legacy format
        exercise_ids = payload.get("exercise_ids") or []
        exercise_plans = [{"exercise_id": ex_id} for ex_id in exercise_ids]
    
    for plan in exercise_plans:
        exercise_data = {
            "exercise_id": plan["exercise_id"],
            "sets": []
        }
        
        # NEW: Store template targets if provided
        if plan.get("target_sets") is not None:
            exercise_data["template_targets"] = {
                "target_sets": plan.get("target_sets"),
                "target_reps": plan.get("target_reps"),
                "target_weight": plan.get("target_weight"),
                "target_unit": plan.get("target_unit", "kg"),
                "set_type": plan.get("set_type", "standard"),
                "rest_seconds": plan.get("rest_seconds", 60)
            }
        
        current_workout["exercises"].append(exercise_data)
```

**Result**: Now the `current_workout` projection will include a `template_targets` field for each exercise that was loaded from a template with target values.

### Step 3: Update Frontend - Display Guided Workout UI

**File**: `frontend/js/app.js`

**Add new method to check if exercise has targets**:
```javascript
// Check if exercise has template targets (guided mode)
hasTemplateTargets(exercise) {
    return exercise.template_targets && exercise.template_targets.target_sets > 0;
},

// Generate planned sets array for display
getPlannedSets(exercise) {
    if (!this.hasTemplateTargets(exercise)) return [];
    
    const targets = exercise.template_targets;
    const plannedSets = [];
    
    for (let i = 0; i < targets.target_sets; i++) {
        plannedSets.push({
            setNumber: i + 1,
            targetWeight: targets.target_weight,
            targetReps: targets.target_reps,
            targetUnit: targets.target_unit || 'kg',
            completed: false
        });
    }
    
    return plannedSets;
},

// Get logged set for a specific planned set number
getLoggedSetForPlannedSet(exercise, setNumber) {
    if (!exercise.sets || setNumber > exercise.sets.length) return null;
    return exercise.sets[setNumber - 1];
},

// Check if a planned set is completed
isPlannedSetCompleted(exercise, setNumber) {
    return setNumber <= (exercise.sets?.length || 0);
},

// Log a planned set with default values from template
async logPlannedSet(exerciseId, setNumber) {
    const exercise = this.currentWorkout.exercises.find(ex => ex.exercise_id === exerciseId);
    if (!exercise || !exercise.template_targets) return;
    
    const targets = exercise.template_targets;
    
    // Pre-fill with target values
    this.selectedExerciseId = exerciseId;
    this.setForm.weight = targets.target_weight || '';
    this.setForm.reps = targets.target_reps || '';
    this.setForm.unit = targets.target_unit || 'kg';
    
    // Open the set logger so user can confirm or adjust
    this.showSetLogger = true;
},

// Quick-log a set (checkbox click) - logs with exact target values
async quickLogPlannedSet(exerciseId) {
    if (!this.currentWorkout) return;
    
    const exercise = this.currentWorkout.exercises.find(ex => ex.exercise_id === exerciseId);
    if (!exercise || !exercise.template_targets) return;
    
    const targets = exercise.template_targets;
    
    try {
        const result = await API.emitEvent('SetLogged', {
            workout_id: this.currentWorkout.id,
            exercise_id: exerciseId,
            weight: targets.target_weight,
            reps: targets.target_reps,
            unit: targets.target_unit || 'kg'
        });
        
        // Check for PR
        if (result.derived && result.derived.is_pr) {
            this.showStatus('NEW PR! Set logged!', 'success');
            delete this.exerciseHistoryCache[exerciseId];
        } else {
            this.showStatus('Set logged!', 'success');
        }
        
        await this.loadCurrentWorkout();
    } catch (error) {
        this.showStatus('Failed to log set: ' + error.message, 'error');
    }
}
```

### Step 4: Update Frontend HTML - Guided Workout Display

**File**: `frontend/index.html`

**Find the exercise list section (around line 208-250)** and update it:

**Current structure**:
```html
<template x-for="exercise in currentWorkout?.exercises" :key="exercise.exercise_id">
    <div class="bg-gray-800 rounded-xl p-4">
        <!-- Exercise Header -->
        <div class="flex justify-between items-center mb-3">
            <h3 class="font-semibold" x-text="getExerciseName(exercise.exercise_id)"></h3>
            <button @click="selectExerciseForSet(exercise.exercise_id)" ...>
                + Set
            </button>
        </div>
        
        <!-- Sets List -->
        <div class="space-y-2">
            <template x-for="(set, idx) in exercise.sets" :key="idx">
                <!-- Set display -->
            </template>
        </div>
    </div>
</template>
```

**Change to** (with guided mode support):
```html
<template x-for="exercise in currentWorkout?.exercises" :key="exercise.exercise_id">
    <div class="bg-gray-800 rounded-xl p-4">
        <!-- Exercise Header -->
        <div class="flex justify-between items-center mb-3">
            <h3 class="font-semibold" x-text="getExerciseName(exercise.exercise_id)"></h3>
            <button
                @click="selectExerciseForSet(exercise.exercise_id)"
                class="bg-green-600 hover:bg-green-700 text-white text-sm px-3 py-1 rounded-lg transition-colors"
            >
                + Set
            </button>
        </div>
        
        <!-- Template Target Summary (if guided mode) -->
        <div x-show="hasTemplateTargets(exercise)" class="mb-3 text-sm text-gray-400">
            <span>Target: </span>
            <span x-text="exercise.template_targets.target_sets"></span> sets × 
            <span x-text="exercise.template_targets.target_reps"></span> reps @ 
            <span x-text="exercise.template_targets.target_weight"></span><span x-text="exercise.template_targets.target_unit"></span>
        </div>
        
        <!-- GUIDED MODE: Planned Sets with Checkboxes -->
        <div x-show="hasTemplateTargets(exercise)" class="space-y-2 mb-3">
            <template x-for="plannedSet in getPlannedSets(exercise)" :key="plannedSet.setNumber">
                <div 
                    class="bg-gray-700 rounded-lg p-3 flex items-center justify-between"
                    :class="{
                        'bg-green-900 border border-green-600': isPlannedSetCompleted(exercise, plannedSet.setNumber),
                        'hover:bg-gray-650 cursor-pointer': !isPlannedSetCompleted(exercise, plannedSet.setNumber)
                    }"
                >
                    <!-- Left: Checkbox and Set Label -->
                    <div class="flex items-center gap-3">
                        <button
                            x-show="!isPlannedSetCompleted(exercise, plannedSet.setNumber)"
                            @click="quickLogPlannedSet(exercise.exercise_id)"
                            class="w-6 h-6 border-2 border-gray-400 rounded hover:border-green-500 transition-colors flex items-center justify-center"
                        >
                        </button>
                        <span
                            x-show="isPlannedSetCompleted(exercise, plannedSet.setNumber)"
                            class="w-6 h-6 bg-green-600 rounded flex items-center justify-center text-white"
                        >
                            ✓
                        </span>
                        <span class="text-sm text-gray-400" x-text="`Set ${plannedSet.setNumber}`"></span>
                    </div>
                    
                    <!-- Right: Target or Actual Values -->
                    <div class="flex items-center gap-3">
                        <!-- If completed, show actual logged values -->
                        <template x-if="isPlannedSetCompleted(exercise, plannedSet.setNumber)">
                            <span class="font-mono text-green-400">
                                <span x-text="getLoggedSetForPlannedSet(exercise, plannedSet.setNumber)?.weight"></span><span x-text="getLoggedSetForPlannedSet(exercise, plannedSet.setNumber)?.unit"></span> × 
                                <span x-text="getLoggedSetForPlannedSet(exercise, plannedSet.setNumber)?.reps"></span>
                            </span>
                        </template>
                        
                        <!-- If not completed, show target values -->
                        <template x-if="!isPlannedSetCompleted(exercise, plannedSet.setNumber)">
                            <span class="font-mono text-gray-300">
                                <span x-text="plannedSet.targetWeight"></span><span x-text="plannedSet.targetUnit"></span> × 
                                <span x-text="plannedSet.targetReps"></span>
                            </span>
                        </template>
                        
                        <!-- Edit/Delete button -->
                        <button
                            x-show="isPlannedSetCompleted(exercise, plannedSet.setNumber)"
                            @click="deleteSet(getLoggedSetForPlannedSet(exercise, plannedSet.setNumber)?.event_id)"
                            class="text-red-400 hover:text-red-300 text-sm"
                            title="Delete set"
                        >
                            ✕
                        </button>
                    </div>
                </div>
            </template>
        </div>
        
        <!-- STANDARD MODE: Logged Sets Only (current behavior) -->
        <div x-show="!hasTemplateTargets(exercise)" class="space-y-2">
            <template x-for="(set, idx) in exercise.sets" :key="idx">
                <div class="bg-gray-700 rounded-lg p-2 flex justify-between items-center">
                    <span class="text-sm text-gray-400" x-text="`Set ${idx + 1}`"></span>
                    <div class="flex items-center gap-3">
                        <span class="font-mono" x-text="`${set.weight}${set.unit} × ${set.reps}`"></span>
                        <button
                            x-show="set.event_id"
                            @click="deleteSet(set.event_id)"
                            class="text-red-400 hover:text-red-300 text-sm"
                            title="Delete set"
                        >
                            ✕
                        </button>
                    </div>
                </div>
            </template>
            <div x-show="exercise.sets.length === 0" class="text-gray-500 text-sm text-center py-2">
                No sets logged yet
            </div>
        </div>
        
        <!-- Extra Sets (beyond planned) in Guided Mode -->
        <div x-show="hasTemplateTargets(exercise) && exercise.sets.length > exercise.template_targets.target_sets" class="mt-3">
            <p class="text-xs text-gray-500 mb-2">Extra Sets:</p>
            <div class="space-y-2">
                <template x-for="(set, idx) in exercise.sets.slice(exercise.template_targets.target_sets)" :key="idx">
                    <div class="bg-gray-700 rounded-lg p-2 flex justify-between items-center">
                        <span class="text-sm text-gray-400" x-text="`Set ${exercise.template_targets.target_sets + idx + 1}`"></span>
                        <div class="flex items-center gap-3">
                            <span class="font-mono" x-text="`${set.weight}${set.unit} × ${set.reps}`"></span>
                            <button
                                x-show="set.event_id"
                                @click="deleteSet(set.event_id)"
                                class="text-red-400 hover:text-red-300 text-sm"
                            >
                                ✕
                            </button>
                        </div>
                    </div>
                </template>
            </div>
        </div>
    </div>
</template>
```

### Step 5: Styling Enhancements

**File**: `frontend/css/styles.css`

Add these styles for better checkbox and completion visuals:

```css
/* Guided Workout Checkbox Animations */
.planned-set-checkbox {
    transition: all 0.2s ease-in-out;
}

.planned-set-checkbox:hover {
    transform: scale(1.1);
}

.completed-set {
    animation: completionPulse 0.5s ease-out;
}

@keyframes completionPulse {
    0% {
        transform: scale(1);
        opacity: 1;
    }
    50% {
        transform: scale(1.05);
        opacity: 0.8;
    }
    100% {
        transform: scale(1);
        opacity: 1;
    }
}

/* Guided mode card enhancements */
.guided-set-row {
    transition: background-color 0.2s ease;
}

.guided-set-row:hover {
    background-color: rgba(55, 65, 81, 0.6);
}
```

## Edge Cases to Handle

### 1. Partial Completion
**Scenario**: User completes Set 1 and Set 2, but wants to stop without doing Set 3.
**Solution**: That's fine - the checkboxes simply show what's been done. Uncompleted sets remain unchecked.

### 2. Exceeding Target Sets
**Scenario**: Template says 3 sets, but user feels good and wants to do 4.
**Solution**: The "+ Set" button remains available. Extra sets appear in an "Extra Sets" section below the planned ones.

### 3. Adjusting Values Mid-Workout
**Scenario**: Template says 100kg, but user only manages 95kg on Set 2.
**Solution**: 
- Option A (Quick): User just checks the box anyway (logs 100kg as prescribed)
- Option B (Accurate): User taps the set row to open edit modal, adjusts to 95kg, then logs

### 4. Templates Without Targets (Legacy)
**Scenario**: User has old templates that only stored exercise IDs.
**Solution**: Use `hasTemplateTargets()` check. If false, show standard mode (current behavior).

### 5. Mixed Templates
**Scenario**: Template has targets for some exercises but not others.
**Solution**: Each exercise independently checks `hasTemplateTargets()`. Some show guided mode, others show standard mode.

### 6. Voice Logging in Guided Mode
**Scenario**: User is in guided mode but uses voice to log a set.
**Solution**: Voice still works as normal. The next unchecked box will appear checked after the voice set is logged.

## Testing Checklist

### Backend Tests
- [ ] Template with `target_sets`, `target_reps`, `target_weight` properly passes to workout
- [ ] Legacy templates (exercise_ids only) still work
- [ ] Mixed format templates work (some exercises with targets, some without)

### Frontend Tests
- [ ] Guided mode displays correctly with checkboxes
- [ ] Clicking checkbox logs set with target values
- [ ] Completing all planned sets works
- [ ] Adding extra sets beyond target_sets works
- [ ] Deleting a completed set unchecks the box
- [ ] Standard mode (no targets) displays as before
- [ ] Voice logging works alongside guided mode

### UX Tests
- [ ] UI is intuitive and easy to understand
- [ ] Checkbox interactions feel responsive
- [ ] Completed vs incomplete sets are visually distinct
- [ ] Card mode still works with guided workouts
- [ ] Template editor shows target values are saved

## Future Enhancements

### 1. Progressive Overload Suggestions
When loading a template that was used before, show the last actual values achieved:
```
Set 1: [ ] 100kg × 10 reps (Last time: 95kg × 10)
```

### 2. Rest Timers
Use the `rest_seconds` field to show countdown timers between sets.

### 3. Advanced Set Types
Support dropsets, supersets, warmup sets with different UI indicators.

### 4. Workout Notes
Allow users to add notes per exercise or per set (e.g., "felt heavy today").

## Summary

This implementation adds **Guided Workout Mode** by:

1. ✅ Passing template target values to the workout when started
2. ✅ Storing those targets in the workout projection
3. ✅ Displaying planned sets with checkboxes in the UI
4. ✅ Allowing quick-log via checkbox click
5. ✅ Supporting extra sets beyond the plan
6. ✅ Maintaining backward compatibility with legacy templates

The result is a clear, actionable workout plan that guides users through their prescribed routine while still allowing flexibility and manual adjustments.


