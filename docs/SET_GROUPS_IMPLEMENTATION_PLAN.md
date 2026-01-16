# Set Groups Implementation Plan

## Problem Statement

Currently, templates support only one target configuration per exercise:
- X sets × Y reps @ Z weight

**Real-world need:**
- Warmup sets → Working sets → Dropsets (different weights)
- Pyramid training (increasing weight, decreasing reps)
- Multiple intensity zones in one exercise

**Example:** Bench Press
- 2 warmup sets: 60kg × 10 reps
- 3 working sets: 100kg × 8 reps  
- 2 dropsets: 70kg × 12 reps

## Solution: Set Groups

Allow multiple "set groups" per exercise, where each group defines:
- Number of sets
- Target reps
- Target weight
- Set type (warmup, working, dropset, etc.)
- Optional notes

## Data Model Changes

### Current Template Exercise Format
```python
{
    "exercise_id": "bench-press",
    "target_sets": 3,
    "target_reps": 10,
    "target_weight": 100,
    "target_unit": "kg",
    "set_type": "standard",
    "rest_seconds": 60
}
```

### New Format (Backward Compatible)
```python
{
    "exercise_id": "bench-press",
    # NEW: set_groups array (if present, takes precedence)
    "set_groups": [
        {
            "target_sets": 2,
            "target_reps": 10,
            "target_weight": 60,
            "target_unit": "kg",
            "set_type": "warmup",
            "rest_seconds": 60,
            "notes": "Warmup"
        },
        {
            "target_sets": 3,
            "target_reps": 8,
            "target_weight": 100,
            "target_unit": "kg",
            "set_type": "working",
            "rest_seconds": 90,
            "notes": "Main working sets"
        },
        {
            "target_sets": 2,
            "target_reps": 12,
            "target_weight": 70,
            "target_unit": "kg",
            "set_type": "dropset",
            "rest_seconds": 60,
            "notes": "Dropset to failure"
        }
    ],
    
    # OLD: single-target fields (kept for backward compatibility)
    "target_sets": 3,
    "target_reps": 10,
    "target_weight": 100,
    "target_unit": "kg",
    "set_type": "standard",
    "rest_seconds": 60
}
```

**Compatibility rule:**
- If `set_groups` exists and has length > 0, use it
- Otherwise, fall back to single-target fields
- Both can coexist (single-target = migration path)

## Implementation Steps

### Step 1: Update Backend Schema

**File:** `backend/api/templates.py`

**Update `TemplateExerciseRequest` model (line ~40):**

```python
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
```

**Update `TemplateExerciseResponse` model (line ~18):**

```python
class SetGroupResponse(BaseModel):
    """A group of sets with the same targets."""
    target_sets: int
    target_reps: Optional[int] = None
    target_weight: Optional[float] = None
    target_unit: str = "kg"
    set_type: str = "working"
    rest_seconds: int = 60
    notes: Optional[str] = None


class TemplateExerciseResponse(BaseModel):
    """Exercise within a template."""
    exercise_id: str
    
    # NEW: set groups
    set_groups: Optional[List[SetGroupResponse]] = None
    
    # OLD: single-target (backward compat)
    target_sets: Optional[int] = None
    target_reps: Optional[int] = None
    target_weight: Optional[float] = None
    target_unit: str = "kg"
    set_type: str = "standard"
    rest_seconds: int = 60
    notes: Optional[str] = None
```

### Step 2: Update Workout Projection

**File:** `backend/events.py`

**In `update_projections` function, `WORKOUT_STARTED` handler (line ~243):**

```python
for plan in exercise_plans:
    exercise_data = {
        "exercise_id": plan["exercise_id"],
        "sets": []
    }
    
    # NEW: Support set groups
    if plan.get("set_groups"):
        exercise_data["template_targets"] = {
            "set_groups": plan["set_groups"]
        }
    # OLD: Single target (backward compat)
    elif plan.get("target_sets") is not None:
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

### Step 3: Frontend Helper Methods

**File:** `frontend/js/app.js`

**Add these new methods:**

```javascript
// Check if exercise uses set groups (new format)
usesSetGroups(exercise) {
    return exercise.template_targets?.set_groups && 
           exercise.template_targets.set_groups.length > 0;
},

// Generate flat array of planned sets from set groups
getPlannedSetsFromGroups(exercise) {
    if (!this.usesSetGroups(exercise)) return [];
    
    const plannedSets = [];
    let globalSetNumber = 1;
    
    exercise.template_targets.set_groups.forEach((group, groupIndex) => {
        for (let i = 0; i < group.target_sets; i++) {
            plannedSets.push({
                setNumber: globalSetNumber++,
                groupIndex: groupIndex,
                groupName: group.notes || group.set_type || `Group ${groupIndex + 1}`,
                targetWeight: group.target_weight,
                targetReps: group.target_reps,
                targetUnit: group.target_unit || 'kg',
                setType: group.set_type || 'working',
                isFirstInGroup: i === 0
            });
        }
    });
    
    return plannedSets;
},

// Get group summary for display
getGroupSummary(group) {
    const weight = group.target_weight ? `${group.target_weight}${group.target_unit}` : 'BW';
    return `${group.target_sets} × ${group.target_reps} @ ${weight}`;
},

// Check if planned set is completed
isPlannedSetCompleted(exercise, setNumber) {
    return setNumber <= (exercise.sets?.length || 0);
},

// Get logged set for a specific planned set number
getLoggedSetForPlannedSet(exercise, setNumber) {
    if (!exercise.sets || setNumber > exercise.sets.length) return null;
    return exercise.sets[setNumber - 1];
},

// Quick-log a planned set from set group
async quickLogPlannedSetFromGroup(exerciseId, plannedSet) {
    if (!this.currentWorkout) return;
    
    try {
        const result = await API.emitEvent('SetLogged', {
            workout_id: this.currentWorkout.id,
            exercise_id: exerciseId,
            weight: plannedSet.targetWeight,
            reps: plannedSet.targetReps,
            unit: plannedSet.targetUnit
        });
        
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

**Update existing `getPlannedSets` method to handle both formats:**

```javascript
// Generate planned sets array for display (handles both old and new formats)
getPlannedSets(exercise) {
    if (!this.hasTemplateTargets(exercise)) return [];
    
    // NEW: Set groups format
    if (this.usesSetGroups(exercise)) {
        return this.getPlannedSetsFromGroups(exercise);
    }
    
    // OLD: Single target format (backward compat)
    const targets = exercise.template_targets;
    const plannedSets = [];
    
    for (let i = 0; i < targets.target_sets; i++) {
        plannedSets.push({
            setNumber: i + 1,
            targetWeight: targets.target_weight,
            targetReps: targets.target_reps,
            targetUnit: targets.target_unit || 'kg',
            setType: targets.set_type || 'standard',
            isFirstInGroup: i === 0
        });
    }
    
    return plannedSets;
},
```

### Step 4: Template Editor UI Updates

**File:** `frontend/index.html`

**Find the template editor exercise display (around line 720) and update:**

```html
<template x-for="(exercise, index) in templateEditorData.exercises" :key="index">
    <div class="bg-gray-800 rounded-xl p-4">
        <!-- Exercise Header -->
        <div class="flex justify-between items-center mb-3">
            <h3 class="font-semibold" x-text="getExerciseName(exercise.exercise_id)"></h3>
            <button
                @click="removeExerciseFromTemplate(index)"
                class="text-red-400 hover:text-red-300 text-sm px-2"
            >
                ✕ Remove
            </button>
        </div>

        <!-- Set Groups Container -->
        <div class="space-y-3">
            <!-- Loop through set groups if they exist -->
            <template x-if="exercise.set_groups && exercise.set_groups.length > 0">
                <div class="space-y-3">
                    <template x-for="(group, groupIdx) in exercise.set_groups" :key="groupIdx">
                        <div class="bg-gray-700 rounded-lg p-3">
                            <!-- Group Header -->
                            <div class="flex justify-between items-center mb-2">
                                <input
                                    type="text"
                                    x-model="group.notes"
                                    placeholder="e.g., Warmup, Working Sets"
                                    class="bg-gray-600 rounded px-2 py-1 text-sm flex-1 mr-2"
                                >
                                <button
                                    @click="exercise.set_groups.splice(groupIdx, 1)"
                                    class="text-red-400 hover:text-red-300 text-xs"
                                >
                                    ✕
                                </button>
                            </div>
                            
                            <!-- Group Values -->
                            <div class="grid grid-cols-4 gap-2">
                                <div>
                                    <label class="block text-xs text-gray-400 mb-1">Sets</label>
                                    <input
                                        type="number"
                                        x-model.number="group.target_sets"
                                        min="1"
                                        class="w-full bg-gray-600 rounded px-2 py-2 text-center"
                                    >
                                </div>
                                <div>
                                    <label class="block text-xs text-gray-400 mb-1">Reps</label>
                                    <input
                                        type="number"
                                        x-model.number="group.target_reps"
                                        min="1"
                                        placeholder="–"
                                        class="w-full bg-gray-600 rounded px-2 py-2 text-center"
                                    >
                                </div>
                                <div>
                                    <label class="block text-xs text-gray-400 mb-1">Weight</label>
                                    <input
                                        type="number"
                                        x-model.number="group.target_weight"
                                        min="0"
                                        step="0.5"
                                        placeholder="–"
                                        class="w-full bg-gray-600 rounded px-2 py-2 text-center"
                                    >
                                </div>
                                <div>
                                    <label class="block text-xs text-gray-400 mb-1">Unit</label>
                                    <select
                                        x-model="group.target_unit"
                                        class="w-full bg-gray-600 rounded px-2 py-2 text-sm"
                                    >
                                        <option value="kg">kg</option>
                                        <option value="lb">lb</option>
                                    </select>
                                </div>
                            </div>
                            
                            <!-- Set Type Selector -->
                            <div class="mt-2">
                                <label class="block text-xs text-gray-400 mb-1">Type</label>
                                <select
                                    x-model="group.set_type"
                                    class="w-full bg-gray-600 rounded px-2 py-1 text-sm"
                                >
                                    <option value="warmup">Warmup</option>
                                    <option value="working">Working</option>
                                    <option value="dropset">Dropset</option>
                                    <option value="pyramid">Pyramid</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                        </div>
                    </template>
                    
                    <!-- Add Group Button -->
                    <button
                        @click="addSetGroupToExercise(index)"
                        class="w-full bg-gray-600 hover:bg-gray-500 text-white py-2 px-4 rounded-lg text-sm transition-colors"
                    >
                        + Add Set Group
                    </button>
                </div>
            </template>

            <!-- OLD FORMAT: Single Target Values (shown if no set groups) -->
            <template x-if="!exercise.set_groups || exercise.set_groups.length === 0">
                <div class="bg-gray-700 rounded-lg p-3">
                    <div class="grid grid-cols-3 gap-3 mb-3">
                        <div class="text-center">
                            <label class="block text-xs text-gray-400 mb-1">Sets</label>
                            <input
                                type="number"
                                x-model.number="exercise.target_sets"
                                placeholder="–"
                                min="1"
                                class="w-full bg-gray-600 rounded-lg px-2 py-2 text-center font-mono text-lg"
                            >
                        </div>
                        <div class="text-center">
                            <label class="block text-xs text-gray-400 mb-1">Reps</label>
                            <input
                                type="number"
                                x-model.number="exercise.target_reps"
                                placeholder="–"
                                min="1"
                                class="w-full bg-gray-600 rounded-lg px-2 py-2 text-center font-mono text-lg"
                            >
                        </div>
                        <div class="text-center">
                            <label class="block text-xs text-gray-400 mb-1">Weight</label>
                            <div class="flex items-center gap-1">
                                <input
                                    type="number"
                                    x-model.number="exercise.target_weight"
                                    placeholder="–"
                                    min="0"
                                    step="0.5"
                                    class="w-full bg-gray-600 rounded-lg px-2 py-2 text-center font-mono text-lg"
                                >
                                <select
                                    x-model="exercise.target_unit"
                                    class="bg-gray-600 rounded-lg px-1 py-2 text-sm"
                                >
                                    <option value="kg">kg</option>
                                    <option value="lb">lb</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Convert to Set Groups Button -->
                    <button
                        @click="convertToSetGroups(index)"
                        class="w-full bg-purple-600 hover:bg-purple-700 text-white py-2 px-4 rounded-lg text-sm transition-colors"
                    >
                        ⚡ Use Set Groups (Advanced)
                    </button>
                </div>
            </template>
        </div>
    </div>
</template>
```

**Add helper methods for template editor:**

```javascript
// Add set group to exercise in template
addSetGroupToExercise(exerciseIndex) {
    const exercise = this.templateEditorData.exercises[exerciseIndex];
    
    // Initialize set_groups array if needed
    if (!exercise.set_groups) {
        exercise.set_groups = [];
    }
    
    // Add new group with defaults
    exercise.set_groups.push({
        target_sets: 3,
        target_reps: 10,
        target_weight: null,
        target_unit: 'kg',
        set_type: 'working',
        rest_seconds: 60,
        notes: ''
    });
},

// Convert single-target to set groups format
convertToSetGroups(exerciseIndex) {
    const exercise = this.templateEditorData.exercises[exerciseIndex];
    
    // Create initial group from existing values
    exercise.set_groups = [{
        target_sets: exercise.target_sets || 3,
        target_reps: exercise.target_reps || 10,
        target_weight: exercise.target_weight || null,
        target_unit: exercise.target_unit || 'kg',
        set_type: 'working',
        rest_seconds: exercise.rest_seconds || 60,
        notes: 'Working Sets'
    }];
},
```

### Step 5: Workout Display with Set Groups

**File:** `frontend/index.html`

**Update exercise display during workout (around line 208):**

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
        
        <!-- SET GROUPS MODE -->
        <div x-show="usesSetGroups(exercise)" class="space-y-3">
            <!-- Group sections with planned sets -->
            <template x-for="plannedSet in getPlannedSets(exercise)" :key="plannedSet.setNumber">
                <div>
                    <!-- Group Header (only on first set of group) -->
                    <div x-show="plannedSet.isFirstInGroup" class="flex items-center gap-2 mb-2 mt-2">
                        <div class="flex-1 border-t border-gray-600"></div>
                        <span class="text-xs text-gray-400 uppercase tracking-wide" x-text="plannedSet.groupName"></span>
                        <div class="flex-1 border-t border-gray-600"></div>
                    </div>
                    
                    <!-- Planned Set Row with Checkbox -->
                    <div 
                        class="bg-gray-700 rounded-lg p-3 flex items-center justify-between"
                        :class="{
                            'bg-green-900 border border-green-600': isPlannedSetCompleted(exercise, plannedSet.setNumber),
                            'hover:bg-gray-650': !isPlannedSetCompleted(exercise, plannedSet.setNumber)
                        }"
                    >
                        <!-- Checkbox and Set Number -->
                        <div class="flex items-center gap-3">
                            <button
                                x-show="!isPlannedSetCompleted(exercise, plannedSet.setNumber)"
                                @click="quickLogPlannedSetFromGroup(exercise.exercise_id, plannedSet)"
                                class="w-6 h-6 border-2 border-gray-400 rounded hover:border-green-500 transition-colors"
                            >
                            </button>
                            <span
                                x-show="isPlannedSetCompleted(exercise, plannedSet.setNumber)"
                                class="w-6 h-6 bg-green-600 rounded flex items-center justify-center text-white"
                            >
                                ✓
                            </span>
                            <span class="text-sm text-gray-400" x-text="`Set ${plannedSet.setNumber}`"></span>
                            <!-- Set Type Badge -->
                            <span 
                                x-show="plannedSet.setType !== 'working'"
                                class="text-xs px-2 py-0.5 rounded"
                                :class="{
                                    'bg-blue-900 text-blue-300': plannedSet.setType === 'warmup',
                                    'bg-orange-900 text-orange-300': plannedSet.setType === 'dropset',
                                    'bg-purple-900 text-purple-300': plannedSet.setType === 'pyramid'
                                }"
                                x-text="plannedSet.setType"
                            ></span>
                        </div>
                        
                        <!-- Target or Actual Values -->
                        <div class="flex items-center gap-3">
                            <template x-if="isPlannedSetCompleted(exercise, plannedSet.setNumber)">
                                <span class="font-mono text-green-400">
                                    <span x-text="getLoggedSetForPlannedSet(exercise, plannedSet.setNumber)?.weight"></span><span x-text="getLoggedSetForPlannedSet(exercise, plannedSet.setNumber)?.unit"></span> × 
                                    <span x-text="getLoggedSetForPlannedSet(exercise, plannedSet.setNumber)?.reps"></span>
                                </span>
                            </template>
                            <template x-if="!isPlannedSetCompleted(exercise, plannedSet.setNumber)">
                                <span class="font-mono text-gray-300">
                                    <span x-text="plannedSet.targetWeight || 'BW'"></span><span x-show="plannedSet.targetWeight" x-text="plannedSet.targetUnit"></span> × 
                                    <span x-text="plannedSet.targetReps"></span>
                                </span>
                            </template>
                            
                            <button
                                x-show="isPlannedSetCompleted(exercise, plannedSet.setNumber)"
                                @click="deleteSet(getLoggedSetForPlannedSet(exercise, plannedSet.setNumber)?.event_id)"
                                class="text-red-400 hover:text-red-300 text-sm"
                            >
                                ✕
                            </button>
                        </div>
                    </div>
                </div>
            </template>
        </div>
        
        <!-- SINGLE TARGET MODE (backward compat) -->
        <div x-show="hasTemplateTargets(exercise) && !usesSetGroups(exercise)" class="space-y-2">
            <!-- Target summary -->
            <div class="text-sm text-gray-400 mb-3">
                Target: <span x-text="exercise.template_targets.target_sets"></span> sets × 
                <span x-text="exercise.template_targets.target_reps"></span> reps @ 
                <span x-text="exercise.template_targets.target_weight"></span><span x-text="exercise.template_targets.target_unit"></span>
            </div>
            
            <!-- Planned sets with checkboxes -->
            <template x-for="plannedSet in getPlannedSets(exercise)" :key="plannedSet.setNumber">
                <!-- Same checkbox UI as before -->
                <div class="bg-gray-700 rounded-lg p-3 flex items-center justify-between">
                    <!-- Checkbox implementation here (same as original plan) -->
                </div>
            </template>
        </div>
        
        <!-- STANDARD MODE (no targets) -->
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
        
        <!-- Extra Sets (beyond all planned groups) -->
        <div x-show="hasTemplateTargets(exercise) && exercise.sets.length > getPlannedSets(exercise).length" class="mt-3">
            <div class="flex items-center gap-2 mb-2">
                <div class="flex-1 border-t border-gray-600"></div>
                <span class="text-xs text-gray-400 uppercase tracking-wide">Extra Sets</span>
                <div class="flex-1 border-t border-gray-600"></div>
            </div>
            <div class="space-y-2">
                <template x-for="(set, idx) in exercise.sets.slice(getPlannedSets(exercise).length)" :key="idx">
                    <div class="bg-gray-700 rounded-lg p-2 flex justify-between items-center">
                        <span class="text-sm text-gray-400" x-text="`Set ${getPlannedSets(exercise).length + idx + 1}`"></span>
                        <div class="flex items-center gap-3">
                            <span class="font-mono" x-text="`${set.weight}${set.unit} × ${set.reps}`"></span>
                            <button
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

### Step 6: Styling Enhancements

**File:** `frontend/css/styles.css`

```css
/* Set type badges */
.set-type-warmup {
    background-color: rgba(59, 130, 246, 0.2);
    color: rgb(147, 197, 253);
}

.set-type-dropset {
    background-color: rgba(251, 146, 60, 0.2);
    color: rgb(253, 186, 116);
}

.set-type-pyramid {
    background-color: rgba(168, 85, 247, 0.2);
    color: rgb(196, 181, 253);
}

/* Group dividers */
.group-divider {
    height: 1px;
    background: linear-gradient(to right, transparent, rgb(75, 85, 99), transparent);
}

/* Hover state for set group fields */
.set-group-input:focus {
    outline: none;
    border-color: rgb(59, 130, 246);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
```

## Migration Strategy

### For Existing Templates
1. Old templates with single targets continue to work (backward compat)
2. Users can click "Use Set Groups (Advanced)" to convert
3. No automatic migration needed

### For New Templates
1. Default to simple single-target mode
2. Advanced users can add set groups when needed
3. Set groups button is visible but not prominent

## Voice Integration

LLM can parse set groups naturally:

**User says:**
> "Bench press: 2 warmup sets of 10 at 60kg, then 3 working sets of 8 at 100kg"

**LLM creates:**
```javascript
{
    exercise_id: "bench-press",
    set_groups: [
        { target_sets: 2, target_reps: 10, target_weight: 60, set_type: "warmup" },
        { target_sets: 3, target_reps: 8, target_weight: 100, set_type: "working" }
    ]
}
```

## Testing Checklist

### Backend
- [ ] Create template with set groups
- [ ] Create template with single target (legacy)
- [ ] Start workout from set groups template
- [ ] Start workout from legacy template
- [ ] API validates set groups structure

### Frontend - Template Editor
- [ ] Add set group button works
- [ ] Remove set group works
- [ ] Convert single-target to set groups works
- [ ] Save template with set groups
- [ ] Edit existing set groups template

### Frontend - Workout Display
- [ ] Set groups display with dividers
- [ ] Checkboxes work for each planned set
- [ ] Set type badges show correctly
- [ ] Group names display
- [ ] Extra sets appear after all groups
- [ ] Legacy single-target templates still work

### Voice
- [ ] Voice can create set groups in template editor
- [ ] Voice logging works during workout with set groups

## Example Use Cases

### Pyramid Training
```
Squat:
- Group 1: 1 × 10 @ 60kg (Warmup)
- Group 2: 1 × 8 @ 80kg
- Group 3: 1 × 6 @ 100kg
- Group 4: 1 × 4 @ 120kg
- Group 5: 1 × 2 @ 140kg (Peak)
```

### Warmup + Working + Dropset
```
Bench Press:
- Group 1: 2 × 12 @ 60kg (Warmup)
- Group 2: 3 × 8 @ 100kg (Working)
- Group 3: 2 × 15 @ 70kg (Dropset)
```

### 5/3/1 Program
```
Deadlift:
- Week 1: 1 × 5 @ 65%, 1 × 5 @ 75%, 1 × 5+ @ 85%
```

## Summary

This implementation adds powerful set group functionality while:
- ✅ Maintaining backward compatibility
- ✅ Keeping the simple mode for basic users
- ✅ Providing advanced flexibility for complex programs
- ✅ Working seamlessly with voice input
- ✅ Displaying clearly during workouts with visual grouping

Users can now create sophisticated templates that match real-world training programs!

