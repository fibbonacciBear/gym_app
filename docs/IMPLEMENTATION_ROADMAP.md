# Implementation Roadmap

## Overview

Two major features to implement:
1. **Guided Workout** - Show planned sets with checkboxes
2. **Set Groups** - Support multiple weight/rep schemes per exercise

## Recommended Order

### Phase 1: Guided Workout (Foundation)
**Priority:** HIGH - Core user request  
**Complexity:** Medium  
**Time:** 2-3 hours

This establishes the checkbox-based UI that Set Groups will build upon.

**Prompt for Claude Code:**
```
Implement the Guided Workout feature described in docs/IMPLEMENTATION_BRIEF.md 
and docs/GUIDED_WORKOUT_IMPLEMENTATION_PLAN.md - add checkboxes to show 
planned sets when starting from templates.
```

**Files Modified:**
- `backend/api/templates.py` - Pass exercise plans to workout
- `backend/events.py` - Store template targets in projection
- `frontend/js/app.js` - Add guided mode helpers
- `frontend/index.html` - Add checkbox UI
- `frontend/css/styles.css` - Add animations

**Test Before Moving On:**
- [ ] Start workout from template shows checkboxes
- [ ] Clicking checkbox logs set with target values
- [ ] Can add extra sets beyond template
- [ ] Legacy templates (no targets) still work
- [ ] Voice logging works alongside checkboxes

### Phase 2: Set Groups (Enhancement)
**Priority:** MEDIUM - Power user feature  
**Complexity:** Medium-High  
**Time:** 3-4 hours

Builds on Phase 1 to support complex training programs.

**Prompt for Claude Code:**
```
Implement set groups feature per docs/SET_GROUPS_IMPLEMENTATION_PLAN.md - 
allow multiple groups of sets at different weights/reps per exercise 
(e.g., warmup sets → working sets → dropsets) while maintaining backward 
compatibility with single-target templates.
```

**Files Modified:**
- `backend/api/templates.py` - Add set groups models
- `backend/events.py` - Handle set groups in projection
- `frontend/js/app.js` - Add set groups helpers
- `frontend/index.html` - Update template editor + workout display
- `frontend/css/styles.css` - Add group styling

**Test After Implementation:**
- [ ] Create template with multiple set groups
- [ ] Each group displays with visual separator
- [ ] Set type badges show (warmup, working, dropset)
- [ ] Checkboxes work across all groups
- [ ] Can convert simple template to set groups
- [ ] Legacy single-target templates still work

## Why This Order?

1. **Foundation First:** Guided Workout establishes the checkbox UI pattern
2. **Incremental Complexity:** Set Groups extends that pattern
3. **User Value:** Users get immediate benefit from Phase 1
4. **Testing:** Each phase can be tested independently
5. **Rollback Safety:** If Phase 2 has issues, Phase 1 still works

## Alternative: Implement Together

If you want both features at once:

**Combined Prompt:**
```
Implement both Guided Workout and Set Groups features:

1. First read docs/IMPLEMENTATION_BRIEF.md and implement the guided workout 
   checkbox UI per docs/GUIDED_WORKOUT_IMPLEMENTATION_PLAN.md

2. Then extend it with set groups per docs/SET_GROUPS_IMPLEMENTATION_PLAN.md 
   to support multiple weight/rep schemes per exercise

This allows users to see planned sets with checkboxes, and advanced users 
can create templates with warmup → working → dropset progressions.
```

## Quick Reference

| Feature | Files | Priority | Builds On |
|---------|-------|----------|-----------|
| Guided Workout | 5 files | HIGH | Nothing |
| Set Groups | Same 5 files | MEDIUM | Guided Workout |

## Support Documents

### For Guided Workout:
- `IMPLEMENTATION_BRIEF.md` - Quick overview
- `GUIDED_WORKOUT_IMPLEMENTATION_PLAN.md` - Detailed guide
- `GUIDED_WORKOUT_UI_MOCKUP.md` - Visual examples
- `CLAUDE_PROMPT.md` - Copy-paste prompt

### For Set Groups:
- `SET_GROUPS_IMPLEMENTATION_PLAN.md` - Detailed guide
- `SET_GROUPS_PROMPT.md` - Copy-paste prompt

## After Implementation

### User-Facing Changes

**Before:**
```
🏋️ Bench Press
No sets logged yet
```

**After Phase 1:**
```
🏋️ Bench Press
Target: 3 sets × 10 reps @ 100kg

[ ] Set 1: 100kg × 10 reps
[ ] Set 2: 100kg × 10 reps
[ ] Set 3: 100kg × 10 reps
```

**After Phase 2:**
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

## Backward Compatibility

Both phases maintain full backward compatibility:
- ✅ Old templates without targets work as before
- ✅ Templates with single targets work (Phase 1)
- ✅ Templates with set groups work (Phase 2)
- ✅ No database migrations needed
- ✅ No breaking changes to API

## Next Steps

1. Choose Phase 1 only or both phases
2. Copy the appropriate prompt from above
3. Share with Claude Code
4. Test after implementation
5. Report any issues or improvements needed

Good luck! 🚀

