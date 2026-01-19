# Future Features

This document tracks planned features and enhancements for the Voice Workout Tracker.

---

## 🎯 Exercise Designer & Personalized Workout Plans

**Status:** Planned  
**Priority:** High  
**Requested by:** User 0

### Overview

An intelligent exercise designer that creates personalized workout plans based on user profile, goals, and physical status. Users will also see detailed muscle engagement info per exercise and track calories burned.

### Requirements

#### User Profile (One-time Input)
Users provide their profile information once, stored and remembered for future plan generation:

- **Age** - For age-appropriate exercise selection and intensity
- **Weight** - Required for accurate calorie calculations
- **Height** (optional) - For BMI/body composition context
- **Fitness Level** - Beginner / Intermediate / Advanced
- **Goals** - Multi-select:
  - Build Muscle
  - Lose Weight / Fat Loss
  - Increase Strength
  - Improve Endurance
  - General Fitness
- **Injuries/Limitations** - Free text for any physical constraints
- **Available Equipment** - Gym / Home / Bodyweight only
- **Days per Week** - Training frequency (1-7)
- **Session Duration** - Preferred workout length in minutes

#### Workout Plan Generation (LLM-Powered)

The system will use an LLM to generate personalized workout plans with contextual guidance:

**Context provided to LLM:**
- User's complete profile (above)
- Available exercises from our exercise library
- Exercise metadata (muscles, difficulty, equipment needed)
- Best practices for the user's stated goals
- Progressive overload principles
- Rest/recovery guidelines

**Output:**
- Weekly workout schedule (e.g., Push/Pull/Legs, Upper/Lower, Full Body)
- Exercise selection per day with:
  - Recommended sets
  - Rep ranges
  - Rest periods
  - Progression notes
- Rationale explaining why exercises were chosen

**Template Integration:**
- Generated plans can be saved as workout templates
- Users can regenerate/tweak plans as goals evolve

#### Muscle Information Per Exercise

Enrich exercise data to include:

```json
{
  "id": "bench-press",
  "name": "Bench Press",
  "category": "chest",
  "primary_muscles": ["pectoralis_major", "anterior_deltoid", "triceps"],
  "secondary_muscles": ["serratus_anterior", "core"],
  "difficulty": "intermediate",
  "equipment": ["barbell", "bench"],
  "met_value": 5.0,
  "instructions": "...",
  "tips": ["Keep shoulder blades retracted", "Control the descent"]
}
```

**UI Display:**
- Show primary/secondary muscles when viewing an exercise
- Consider future enhancement: interactive muscle diagram (SVG body map)

#### Calorie Tracking (All Levels)

Track and display calories burned at three granularities:

1. **Per-Set** - Estimated calories for each logged set
2. **Per-Exercise** - Sum of all sets for that exercise
3. **Total Workout** - Complete session calorie burn

**Calculation Method:**
Using MET (Metabolic Equivalent of Task) values:

```
Calories = MET × Weight(kg) × Duration(hours)
```

**Estimation factors:**
- Exercise MET value (3-6 for weight training, varies by intensity)
- User's body weight (from profile)
- Set duration estimate:
  - Time under tension (based on reps × ~3 seconds)
  - Rest periods (configurable, default 60-90 seconds)
  - Active recovery movements

**Display locations:**
- Set logging modal: Show estimated calories after logging
- Exercise card: Running calorie total
- Workout summary: Total calories with breakdown
- History: Historical calorie data per workout

---

### Implementation Phases

| Phase | Deliverable | Effort | Dependencies |
|-------|-------------|--------|--------------|
| **1** | Enrich `exercises.json` with muscles, MET values, equipment | Low | None |
| **2** | User profile schema and storage (backend) | Medium | None |
| **3** | Profile input UI (settings/onboarding) | Medium | Phase 2 |
| **4** | Display muscle info in exercise cards/modals | Low | Phase 1 |
| **5** | Calorie calculation engine | Medium | Phase 1, 2 |
| **6** | Calorie display in UI (set/exercise/workout) | Medium | Phase 5 |
| **7** | LLM integration for plan generation | High | Phase 1, 2 |
| **8** | Plan designer UI wizard | High | Phase 7 |
| **9** | (Future) Interactive muscle diagram visualization | Medium | Phase 4 |

---

### Data Model Changes

#### New: User Profile Table

```sql
CREATE TABLE user_profiles (
    user_id TEXT PRIMARY KEY,
    age INTEGER,
    weight_kg REAL,
    height_cm REAL,
    fitness_level TEXT,  -- 'beginner', 'intermediate', 'advanced'
    goals TEXT,          -- JSON array of goal strings
    limitations TEXT,    -- Free text
    equipment TEXT,      -- JSON array of available equipment
    days_per_week INTEGER,
    session_duration_minutes INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### Updated: Exercise Schema

```sql
-- exercises.json or exercises table
{
    id: TEXT,
    name: TEXT,
    category: TEXT,
    primary_muscles: TEXT[],      -- NEW
    secondary_muscles: TEXT[],    -- NEW
    difficulty: TEXT,             -- NEW: 'beginner', 'intermediate', 'advanced'
    equipment: TEXT[],            -- NEW
    met_value: REAL,              -- NEW: for calorie calculation
    instructions: TEXT,           -- NEW
    tips: TEXT[]                  -- NEW
}
```

#### Updated: Workout Stats

Add calorie fields to workout completion data:

```json
{
  "workout_id": "...",
  "stats": {
    "exercise_count": 5,
    "total_sets": 20,
    "total_volume": 5000,
    "total_calories": 320,        // NEW
    "duration_minutes": 55        // NEW (if we add timing)
  }
}
```

---

### UX Considerations

1. **Non-blocking Profile**: Users can use the app without a profile; calorie tracking and plan generation simply won't be available until profile is set.

2. **Profile Prompt**: After a few workouts, gently prompt users to complete their profile to unlock features.

3. **Quick Update**: Allow users to update just their weight (most frequently changing metric) without re-entering everything.

4. **Goal Evolution**: Make it easy to update goals as users progress (e.g., from "Lose Weight" to "Build Muscle").

5. **Plan Regeneration**: Users should be able to request a new plan anytime with updated parameters.

---

### Open Questions

- [ ] Should we store historical weight to track body composition over time?
- [x] Do we want to integrate with health APIs (Apple Health, Google Fit) for weight sync? → **Yes, see "Health Platform Integrations" section below**
- [ ] Should calorie display be optional/hideable for users who find it distracting?
- [x] What LLM provider to use? → **Supporting both OpenAI and Anthropic (configurable)**
- [x] Should templates support target sets/reps/weights? → **Yes, see Sprint 7**
- [x] Should we have guided workout execution? → **Yes, see Sprint 8**
- [x] Should we support weekly programs? → **Yes, see Sprint 9**
- [x] Should we have auto-progression? → **Yes, see Sprint 9.5**
- [x] Should we ship pre-built programs? → **Yes, StrongLifts & PPL in Sprint 9**

---

## 🏋️ Workout Execution & Program Planning

**Status:** In Progress (Sprints 7-9.5)  
**Priority:** Critical  
**Requested by:** User testing feedback

### Problem Statement

The app currently conflates two distinct concepts:
1. **Workout Template Creation** - Defining *what* a workout should include
2. **Workout Execution** - Actually *performing* the workout and recording progress

### Solution: Home Screen Redesign

Three buttons that map to distinct user intents:

| Button | User Intent | Action |
|--------|-------------|--------|
| **Today's Workout** | "I have a plan, execute it" | Load scheduled template into Execution Mode |
| **Plan Builder** | "I want to design/edit programs" | Open planning modal |
| **Quick Start** | "Just let me lift" | Start empty workout, add exercises ad-hoc |

### Key Features

- **Sprint 7:** Home screen redesign, enhanced templates with target sets/reps/weights
- **Sprint 8:** Guided execution mode with set status (completed/failed/skipped), rest timer
- **Sprint 9:** Weekly programs, pre-built template library (StrongLifts, PPL)
- **Sprint 9.5:** Progressive overload with auto-progression

See `implementation_plan.md` for full details.

---

## 📋 Other Planned Features

### 📊 Templates Without Specific Weights

**Status:** Supported (Sprint 7)  
**Priority:** Medium

Templates can have `target_weight: null` for shareable/generic templates. Weights can be:
- Entered manually when starting workout
- Auto-populated from history (post-MVP)
- Calculated as % of training max (post-MVP)

### 🔄 Custom Progression Rules (Future)

**Status:** Planned  
**Priority:** Medium  
**Dependencies:** Sprint 9.5

Visual IF/THEN rule builder for advanced users:
- "If completion >= 100% AND avg RPE <= 7, increase weight by 10 lbs"
- "If 2 consecutive failures, deload 10%"

### 🔗 Progression Groups (Future)

**Status:** Planned  
**Priority:** Low  
**Dependencies:** Sprint 9.5

Link multiple templates to share progression state for common exercises (e.g., Push A and Push B both progress bench press together).

---

## 🔗 Health Platform Integrations (Apple Health, Fitbit, Google Fit)

**Status:** Planned  
**Priority:** Medium  
**Estimated Effort:** High (requires native app development)

### Overview

Sync workout data bidirectionally with popular health platforms to give users a unified view of their fitness data and leverage existing health ecosystems.

### Supported Platforms

| Platform | Read | Write | Native App Required |
|----------|------|-------|---------------------|
| **Apple Health** (HealthKit) | ✓ | ✓ | Yes (iOS) |
| **Google Fit** | ✓ | ✓ | Yes (Android) or Web OAuth |
| **Fitbit** | ✓ | ✓ | No (Web API) |
| **Garmin Connect** | ✓ | ✓ | No (Web API) |
| **Samsung Health** | ✓ | ✓ | Yes (Android) |

### Data Sync Capabilities

#### Write to Health Platforms (Export)
After completing a workout, push:

| Data Type | Apple Health | Google Fit | Fitbit |
|-----------|--------------|------------|--------|
| Workout session | `HKWorkout` | `Sessions` | `Activity Log` |
| Calories burned | `activeEnergyBurned` | `calories.expended` | `calories` |
| Duration | `duration` | `duration` | `duration` |
| Exercise type | `workoutActivityType` | `activity.type` | `activityType` |

#### Read from Health Platforms (Import)
Pull user data to personalize experience:

| Data Type | Use Case |
|-----------|----------|
| **Weight** | Auto-update profile for calorie calculations |
| **Resting heart rate** | Estimate workout intensity zones |
| **Sleep data** | Recovery recommendations |
| **Steps** | Overall activity context |
| **Other workouts** | Avoid overtraining (see if user ran 10 miles yesterday) |

### Technical Implementation

#### Apple Health (HealthKit)
- **Requirement:** Native iOS app (Swift/SwiftUI or React Native)
- **Permissions:** Request specific data types at runtime
- **Background sync:** Use `HKObserverQuery` for real-time updates

```swift
// Example: Write workout to HealthKit
let workout = HKWorkout(
    activityType: .traditionalStrengthTraining,
    start: startDate,
    end: endDate,
    duration: duration,
    totalEnergyBurned: HKQuantity(unit: .kilocalorie(), doubleValue: calories),
    totalDistance: nil,
    metadata: ["WorkoutID": workoutId]
)
healthStore.save(workout)
```

#### Google Fit (REST API)
- **Requirement:** OAuth 2.0 authentication
- **Scopes needed:**
  - `fitness.activity.write`
  - `fitness.body.read`
  - `fitness.activity.read`

```javascript
// Example: Write session to Google Fit
POST https://www.googleapis.com/fitness/v1/users/me/sessions
{
  "id": "workout-uuid",
  "name": "Strength Training",
  "startTimeMillis": 1702123456000,
  "endTimeMillis": 1702127056000,
  "activityType": 80  // Weight training
}
```

#### Fitbit (Web API)
- **Requirement:** OAuth 2.0 (can work from PWA/web)
- **Rate limits:** 150 requests/hour per user
- **Scopes:** `activity`, `weight`, `heartrate`, `sleep`

```javascript
// Example: Log activity to Fitbit
POST https://api.fitbit.com/1/user/-/activities.json
{
  "activityId": 3015,  // Weight training
  "startTime": "09:30",
  "durationMillis": 3600000,
  "date": "2024-12-09",
  "calories": 350
}
```

### User Experience

#### Settings Page
```
Health Integrations
─────────────────────────────
Apple Health     [Connected ✓]  [Disconnect]
  ├─ Export workouts: ON
  ├─ Import weight: ON
  └─ Last sync: 2 min ago

Fitbit           [Connect]
  └─ Not connected

Google Fit       [Connected ✓]  [Disconnect]
  ├─ Export workouts: ON
  └─ Last sync: 1 hour ago
```

#### Sync Triggers
1. **Auto-sync on workout completion** - Push data immediately
2. **Background sync** - Periodic pull of weight/body metrics
3. **Manual sync** - User-triggered "Sync Now" button
4. **On app launch** - Pull latest profile data

#### Conflict Resolution
If user logs workout in both our app and Fitbit:
- Deduplicate by timestamp (±5 min window)
- Prefer our app's data (more detailed sets/reps)
- Show "Imported from Fitbit" badge for external workouts

### Implementation Phases

| Phase | Deliverable | Effort | Platform |
|-------|-------------|--------|----------|
| **1** | Fitbit OAuth + export workouts | Medium | Web/PWA |
| **2** | Fitbit import weight | Low | Web/PWA |
| **3** | Google Fit OAuth + export | Medium | Web/Android |
| **4** | Google Fit import metrics | Low | Web/Android |
| **5** | iOS app scaffold | High | iOS |
| **6** | Apple HealthKit integration | High | iOS |
| **7** | Samsung Health (stretch) | Medium | Android |
| **8** | Garmin Connect (stretch) | Medium | Web |

### Privacy & Compliance

- **HIPAA consideration:** Health data requires careful handling
- **User consent:** Explicit opt-in for each integration
- **Data minimization:** Only request scopes we actually use
- **Deletion:** When user disconnects, remove stored tokens
- **Transparency:** Show exactly what data is being synced

### Open Questions

- [ ] Should we store health platform data locally or just pass-through?
- [ ] How to handle users with multiple platforms connected?
- [ ] Should we show heart rate zones if user has HR data?
- [ ] Offer "smart rest timer" based on real-time heart rate?

---

## 📱 Native Mobile App

**Status:** Planned (Dependency for Apple Health)  
**Priority:** High  
**Estimated Effort:** Very High

### Overview

Build native iOS and Android apps to unlock platform-specific features like HealthKit, widgets, and better offline support.

### Technology Options

| Option | Pros | Cons |
|--------|------|------|
| **React Native** | Code sharing, large ecosystem | Bridge overhead, native feel |
| **Flutter** | Fast development, beautiful UI | Dart learning curve |
| **SwiftUI + Kotlin** | Best native experience | Two codebases to maintain |
| **Capacitor/Ionic** | Wrap existing web app | Limited native features |

### Native-Only Features

| Feature | iOS | Android |
|---------|-----|---------|
| HealthKit/Health Connect | ✓ | ✓ |
| Widgets (today's workout) | ✓ | ✓ |
| Watch app | ✓ Apple Watch | ✓ Wear OS |
| Siri/Google Assistant | ✓ | ✓ |
| Offline mode | ✓ | ✓ |
| Push notifications | ✓ | ✓ |
| Background audio (voice) | ✓ | ✓ |

### Recommended Path

1. **Phase 1:** Capacitor wrapper of existing PWA (quick win)
2. **Phase 2:** Add native modules for HealthKit/Health Connect
3. **Phase 3:** Build native widgets
4. **Phase 4:** Apple Watch / Wear OS companion apps

---

## ⌚ Wearable Integration

**Status:** Planned  
**Priority:** Medium  
**Estimated Effort:** High

### Apple Watch App
- Start/stop workout from wrist
- Voice logging via watch microphone
- Show current exercise and last set
- Haptic feedback on set logged

### Wear OS App
- Similar feature set to Apple Watch
- Material You design language

---

*Last updated: December 2024*

