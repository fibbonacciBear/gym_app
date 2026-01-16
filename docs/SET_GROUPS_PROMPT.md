# Prompt for Claude Code: Set Groups Feature

## One-Line Prompt

**"Implement set groups feature per `docs/SET_GROUPS_IMPLEMENTATION_PLAN.md` - allow multiple groups of sets at different weights/reps per exercise (e.g., warmup sets → working sets → dropsets) while maintaining backward compatibility with single-target templates."**

## Context

Currently templates only support one target configuration per exercise:
- 3 sets × 10 reps @ 100kg

Real-world need:
- **Warmup → Working → Dropsets** (different weights)
- **Pyramid training** (increasing weight, decreasing reps)
- **5/3/1 programs** (different intensities per set)

## What to Build

Allow exercises to have multiple "set groups":

```
🏋️ Bench Press
━━━━━━ Warmup ━━━━━━
[ ] Set 1: 60kg × 10 reps
[ ] Set 2: 60kg × 10 reps

━━━━━ Working Sets ━━━━━
[ ] Set 3: 100kg × 8 reps
[ ] Set 4: 100kg × 8 reps
[ ] Set 5: 100kg × 8 reps

━━━━━━ Dropset ━━━━━━
[ ] Set 6: 70kg × 12 reps
[ ] Set 7: 70kg × 12 reps
```

## Implementation Overview

### Backend Changes
1. Add `SetGroupRequest` and `SetGroupResponse` models to `backend/api/templates.py`
2. Add `set_groups` array field to `TemplateExerciseRequest/Response` (alongside existing single-target fields for backward compat)
3. Update `backend/events.py` workout projection to store `set_groups` in `template_targets`

### Frontend Changes
4. Add helper methods to `frontend/js/app.js`:
   - `usesSetGroups(exercise)` - check if new format
   - `getPlannedSetsFromGroups(exercise)` - flatten groups to checkboxes
   - `getGroupSummary(group)` - format display text
   
5. Update template editor in `frontend/index.html`:
   - Show set groups with "+ Add Set Group" button
   - Each group has: sets, reps, weight, type, notes
   - "Convert to Set Groups" button for simple → advanced
   
6. Update workout display in `frontend/index.html`:
   - Visual dividers between groups
   - Group name labels (Warmup, Working, Dropset, etc.)
   - Set type badges with colors
   
7. Add styling in `frontend/css/styles.css`:
   - Set type badges (warmup=blue, dropset=orange, pyramid=purple)
   - Group dividers

## Key Requirements

✅ **Backward compatible** - Single-target templates must still work  
✅ **Optional** - Simple mode by default, set groups for advanced users  
✅ **Visual grouping** - Clear separators between set groups during workout  
✅ **Set type badges** - Color-coded (warmup, working, dropset, pyramid)  

## Data Structure

```python
# NEW format (takes precedence if present)
{
    "exercise_id": "bench-press",
    "set_groups": [
        {
            "target_sets": 2,
            "target_reps": 10,
            "target_weight": 60,
            "target_unit": "kg",
            "set_type": "warmup",
            "notes": "Warmup"
        },
        {
            "target_sets": 3,
            "target_reps": 8,
            "target_weight": 100,
            "set_type": "working",
            "notes": "Main sets"
        }
    ]
}

# OLD format (still supported)
{
    "exercise_id": "bench-press",
    "target_sets": 3,
    "target_reps": 10,
    "target_weight": 100,
    "target_unit": "kg"
}
```

**Compatibility rule:** If `set_groups` exists and has items, use it. Otherwise, fall back to single-target fields.

## Read These Files

- `docs/SET_GROUPS_IMPLEMENTATION_PLAN.md` - Complete step-by-step guide with code examples
- `docs/GUIDED_WORKOUT_IMPLEMENTATION_PLAN.md` - Context on the checkbox UI this builds upon

## Testing

Test scenarios:
1. Create template with set groups (warmup + working)
2. Create template with single target (legacy)
3. Start workout from set groups template → see visual grouping
4. Start workout from legacy template → see old UI
5. Convert single-target to set groups in editor
6. Log sets across different groups with checkboxes

## Notes

- This builds on the Guided Workout feature (checkbox-based set tracking)
- Set groups are optional - simple single-target mode remains default
- Voice integration can naturally parse "2 warmup sets of 10 at 60kg, then 3 working sets of 8 at 100kg"
- All existing templates continue working without migration

