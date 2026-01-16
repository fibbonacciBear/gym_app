# Implementation Brief: Guided Workout Feature

## TL;DR

Add checkboxes to workout exercises started from templates so users can:
1. See their planned sets/reps/weights laid out before they start
2. Check off each set as they complete it
3. Track progress through their workout visually

## Current Problem

When starting a workout from a template:
- User only sees empty exercises with 0 sets
- Template stores `target_sets`, `target_reps`, `target_weight` but this data is NOT shown to the user
- User has no guidance on what they're supposed to do

## What to Build

### UI Changes
Show planned sets with checkboxes:
```
🏋️ Bench Press
Target: 3 sets × 10 reps @ 100kg

[ ] Set 1: 100kg × 10 reps
[ ] Set 2: 100kg × 10 reps  
[ ] Set 3: 100kg × 10 reps

+ Add Set
```

### Interactions
- **Click checkbox**: Logs set with target values immediately
- **Click set row**: Opens edit modal to adjust before logging
- **After completion**: Checkbox shows ✓, displays actual logged values
- **Extra sets**: "+ Set" button adds sets beyond template plan

## Implementation Steps

### 1. Backend: Pass template targets to workout
**File**: `backend/api/templates.py` line ~208

Change `WorkoutStarted` payload to include:
```python
"exercise_plans": exercise_plans  # Full exercise specs with targets
```

### 2. Backend: Store targets in workout projection
**File**: `backend/events.py` line ~243

Add `template_targets` field to each exercise:
```python
exercise_data["template_targets"] = {
    "target_sets": plan.get("target_sets"),
    "target_reps": plan.get("target_reps"),
    "target_weight": plan.get("target_weight"),
    # ... other fields
}
```

### 3. Frontend: Add helper methods
**File**: `frontend/js/app.js`

Add methods:
- `hasTemplateTargets(exercise)` - check if guided mode
- `getPlannedSets(exercise)` - generate checkbox array
- `quickLogPlannedSet(exerciseId)` - log via checkbox click
- `isPlannedSetCompleted(exercise, setNumber)` - check completion

### 4. Frontend: Update HTML
**File**: `frontend/index.html` line ~208

Replace exercise display section with:
- Show target summary (if has targets)
- Loop through planned sets with checkboxes
- Show actual logged values for completed sets
- Show "Extra Sets" section if user goes beyond plan
- Fall back to current UI for exercises without targets

### 5. Styling
**File**: `frontend/css/styles.css`

Add animations and hover states for checkboxes.

## Key Design Decisions

1. **Backward Compatible**: Legacy templates (no targets) still work with current UI
2. **Mixed Templates**: Some exercises can have targets, others don't
3. **Flexible**: User can adjust values before logging or add extra sets
4. **Voice Compatible**: Voice logging still works, updates checkboxes automatically

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `backend/api/templates.py` | ~208-217 | Add `exercise_plans` to workout payload |
| `backend/events.py` | ~243-264 | Store `template_targets` in projection |
| `frontend/js/app.js` | Add new | Add 5-6 new methods for guided mode |
| `frontend/index.html` | ~208-250 | Replace exercise display section |
| `frontend/css/styles.css` | Add new | Add checkbox animations |

## Testing

Test these scenarios:
1. ✅ Template with targets shows checkboxes
2. ✅ Clicking checkbox logs set
3. ✅ Editing set before logging works
4. ✅ Adding extra sets works
5. ✅ Legacy templates (no targets) show old UI
6. ✅ Voice logging updates checkboxes
7. ✅ Deleting a set unchecks the box

## Expected Outcome

Users can start "Today's Workout" and see a clear, actionable plan:
- Know exactly what to do (no guessing)
- Track progress visually (checkboxes)
- Feel satisfaction completing sets (gamification)
- Still have flexibility to adjust (edit values, add sets)

## Reference Documents

- **Full Implementation Plan**: `docs/GUIDED_WORKOUT_IMPLEMENTATION_PLAN.md`
- **UI Mockups**: `docs/GUIDED_WORKOUT_UI_MOCKUP.md`

## Priority

HIGH - Core user request for better template experience.


