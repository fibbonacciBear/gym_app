# Guided Workout UI Mockup

## Before (Current State)

```
┌────────────────────────────────────┐
│  🏋️ Bench Press            + Set   │
├────────────────────────────────────┤
│                                    │
│  No sets logged yet                │
│                                    │
└────────────────────────────────────┘
```

User sees empty exercise - no guidance on what to do.

## After (Guided Mode)

```
┌────────────────────────────────────┐
│  🏋️ Bench Press            + Set   │
│  Target: 3 sets × 10 reps @ 100kg  │
├────────────────────────────────────┤
│  [ ] Set 1    100kg × 10 reps      │
│  [ ] Set 2    100kg × 10 reps      │
│  [ ] Set 3    100kg × 10 reps      │
└────────────────────────────────────┘
```

User sees exactly what to do - just tick the boxes!

## During Workout (Partially Complete)

```
┌────────────────────────────────────┐
│  🏋️ Bench Press            + Set   │
│  Target: 3 sets × 10 reps @ 100kg  │
├────────────────────────────────────┤
│  [✓] Set 1    100kg × 10 reps  ✕   │
│  [✓] Set 2    100kg × 10 reps  ✕   │
│  [ ] Set 3    100kg × 10 reps      │
└────────────────────────────────────┘
```

Progress is visible. User knows they have 1 more set to go.

## With User Adjustments

```
┌────────────────────────────────────┐
│  🏋️ Bench Press            + Set   │
│  Target: 3 sets × 10 reps @ 100kg  │
├────────────────────────────────────┤
│  [✓] Set 1    100kg × 10 reps  ✕   │
│  [✓] Set 2    95kg × 8 reps    ✕   │ ← User adjusted
│  [ ] Set 3    100kg × 10 reps      │
└────────────────────────────────────┘
```

User can adjust values - shows actual vs target.

## With Extra Sets

```
┌────────────────────────────────────┐
│  🏋️ Bench Press            + Set   │
│  Target: 3 sets × 10 reps @ 100kg  │
├────────────────────────────────────┤
│  [✓] Set 1    100kg × 10 reps  ✕   │
│  [✓] Set 2    100kg × 10 reps  ✕   │
│  [✓] Set 3    100kg × 10 reps  ✕   │
├────────────────────────────────────┤
│  Extra Sets:                       │
│  Set 4    100kg × 6 reps       ✕   │ ← User went beyond plan
└────────────────────────────────────┘
```

User can do more than planned - extra sets clearly labeled.

## Standard Mode (No Template Targets)

```
┌────────────────────────────────────┐
│  🏋️ Squats                 + Set   │
├────────────────────────────────────┤
│  Set 1    140kg × 5 reps       ✕   │
│  Set 2    140kg × 5 reps       ✕   │
│  Set 3    140kg × 4 reps       ✕   │
└────────────────────────────────────┘
```

Exercises without targets use current behavior (free-form logging).

## User Interactions

### Quick Log (One-Tap)
```
User taps checkbox [ ] → 
  ↓
  Logs set with exact target values
  ↓
  Checkbox becomes [✓] 
```

**Use case**: "I did exactly what the plan said - just check it off!"

### Adjust and Log (Two-Tap)
```
User taps set row →
  ↓
  Modal opens with pre-filled target values
  ↓
  User adjusts weight/reps
  ↓
  User taps "Log Set"
  ↓
  Checkbox becomes [✓] with actual values shown
```

**Use case**: "I couldn't quite hit the target weight, let me log what I actually did."

### Add Extra Set
```
User taps "+ Set" button →
  ↓
  Modal opens with last set's values pre-filled
  ↓
  User logs the extra set
  ↓
  Extra set appears below planned sets
```

**Use case**: "I'm feeling strong today, let me do one more set!"

## Voice Integration

Voice commands work seamlessly with guided mode:

```
Voice: "100 for 10"
  ↓
Next unchecked box becomes checked
  ↓
Shows as: [✓] Set 2    100kg × 10 reps
```

User can mix voice and touch interactions freely.

## Mobile-Optimized Design

The checkboxes and set rows are:
- ✅ Large tap targets (44px minimum)
- ✅ High contrast for outdoor visibility
- ✅ Haptic feedback on check/uncheck (if supported)
- ✅ Smooth animations for satisfaction
- ✅ Color-coded: gray (todo) → green (done)

## Key Visual Indicators

| State | Checkbox | Row Color | Text Color |
|-------|----------|-----------|------------|
| Pending | `[ ]` | Gray (bg-gray-700) | White |
| Completed | `[✓]` | Green (bg-green-900) | Green text |
| Hover | `[ ]` | Lighter gray | White |

## Complete Workout View

```
┌──────────────────────────────────────────┐
│  Current Workout              [🎤 Card]  │
├──────────────────────────────────────────┤
│                                          │
│  🏋️ Bench Press               + Set     │
│  Target: 3 sets × 10 reps @ 100kg       │
│  [✓] Set 1    100kg × 10  ✕             │
│  [✓] Set 2    100kg × 10  ✕             │
│  [✓] Set 3    100kg × 10  ✕             │
│                                          │
│  🏋️ Overhead Press            + Set     │
│  Target: 3 sets × 8 reps @ 60kg         │
│  [✓] Set 1    60kg × 8    ✕             │
│  [✓] Set 2    60kg × 8    ✕             │
│  [ ] Set 3    60kg × 8                  │
│                                          │
│  🏋️ Squats                    + Set     │
│  Set 1    140kg × 5        ✕             │ ← No targets
│  Set 2    140kg × 5        ✕             │
│                                          │
├──────────────────────────────────────────┤
│  [Discard]              [Finish]         │
└──────────────────────────────────────────┘
```

Clear progress across entire workout - user sees exactly what's left to do.

## Benefits

1. **Mental Clarity**: User knows exactly what to do - no decision fatigue
2. **Progress Tracking**: Visual completion percentage at a glance
3. **Motivation**: Checking boxes gives satisfaction and momentum
4. **Flexibility**: Can still adjust values or add extra sets
5. **Backward Compatible**: Old templates and free-form workouts still work
6. **Voice Compatible**: Works alongside voice logging


