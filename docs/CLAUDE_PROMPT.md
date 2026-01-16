# Prompt for Claude 3.5

Copy and paste this to start the implementation:

---

## Task: Implement Guided Workout Feature

I need you to implement a "Guided Workout" feature that displays planned sets with checkboxes when a user starts a workout from a template.

### Context
- App: Voice-first workout tracker (FastAPI backend + Alpine.js frontend)
- Templates already store: `target_sets`, `target_reps`, `target_weight` per exercise
- Problem: When starting from template, these targets are NOT shown to users
- Solution: Display planned sets with checkboxes that users can tick off as they complete them

### What to Build

Show exercises like this:
```
🏋️ Bench Press
Target: 3 sets × 10 reps @ 100kg

[ ] Set 1: 100kg × 10 reps
[ ] Set 2: 100kg × 10 reps  
[ ] Set 3: 100kg × 10 reps

+ Add Set
```

**User Interactions:**
- Click checkbox → logs set with target values
- Click set row → opens edit modal to adjust before logging
- After logging → checkbox shows ✓ and displays actual values
- Can add extra sets beyond template plan

### Implementation Steps

1. **Backend** (`backend/api/templates.py` ~line 208):
   - Modify `start_from_template` to pass `exercise_plans` (full exercise specs) to `WorkoutStarted` event
   
2. **Backend** (`backend/events.py` ~line 243):
   - Update `WORKOUT_STARTED` handler to store `template_targets` in each exercise's projection
   
3. **Frontend** (`frontend/js/app.js`):
   - Add methods: `hasTemplateTargets()`, `getPlannedSets()`, `quickLogPlannedSet()`, `isPlannedSetCompleted()`
   
4. **Frontend** (`frontend/index.html` ~line 208):
   - Update exercise display to show planned sets with checkboxes when `hasTemplateTargets()` is true
   - Fall back to current UI when false (backward compatibility)
   
5. **Styling** (`frontend/css/styles.css`):
   - Add checkbox animations and completion styles

### Key Requirements

- ✅ Backward compatible with templates that have no targets
- ✅ Support mixed templates (some exercises with targets, some without)
- ✅ Allow editing values before logging
- ✅ Support extra sets beyond plan
- ✅ Work with voice logging (voice updates checkboxes)

### Reference Documents

Read these for detailed guidance:
1. `docs/IMPLEMENTATION_BRIEF.md` - Quick overview
2. `docs/GUIDED_WORKOUT_IMPLEMENTATION_PLAN.md` - Complete step-by-step plan with code examples
3. `docs/GUIDED_WORKOUT_UI_MOCKUP.md` - Visual mockups and UX flows

### Getting Started

Start with Step 1 (backend changes to pass template data), then move to frontend display. Test after each step. Let me know if you need clarification on any part.

---

**Note**: The codebase already has all the infrastructure - we just need to pass the template target data through to the workout and display it with checkboxes.


