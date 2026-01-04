#!/usr/bin/env python3
"""Test database connectivity and basic operations."""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import USE_POSTGRES, DATABASE_URL
from backend.database import (
    init_database,
    append_event,
    get_events,
    set_projection,
    get_projection,
    load_default_exercises,
    get_exercises
)


def test_connection():
    """Test database connection."""
    print("=" * 60)
    print("DATABASE CONNECTION TEST")
    print("=" * 60)
    
    if USE_POSTGRES:
        print(f"✓ Using PostgreSQL")
        print(f"  Connection: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    else:
        print(f"✓ Using SQLite")
        print(f"  Database: workspace/default/gym.db")
    
    print()


def test_tables():
    """Test table initialization."""
    print("=" * 60)
    print("TABLE INITIALIZATION TEST")
    print("=" * 60)
    
    try:
        init_database("default")
        print("✓ Database initialized successfully")
        print("  Tables created: events, projections, exercises")
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        return False
    
    print()
    return True


def test_events():
    """Test event operations."""
    print("=" * 60)
    print("EVENT OPERATIONS TEST")
    print("=" * 60)
    
    try:
        # Append a test event
        event = append_event(
            event_id="test-event-001",
            event_type="WorkoutStarted",
            payload={"workout_id": "test-workout", "name": "Test Workout"},
            user_id="default"
        )
        print(f"✓ Event appended: {event['event_id']}")
        
        # Retrieve events
        events = get_events(user_id="default", limit=10)
        print(f"✓ Retrieved {len(events)} events")
        
        if events:
            print(f"  Most recent: {events[0]['event_type']} at {events[0]['timestamp']}")
    
    except Exception as e:
        print(f"✗ Event operations failed: {e}")
        return False
    
    print()
    return True


def test_projections():
    """Test projection operations."""
    print("=" * 60)
    print("PROJECTION OPERATIONS TEST")
    print("=" * 60)
    
    try:
        # Set a projection
        test_data = {"workout_id": "test-workout", "exercises": []}
        set_projection("current_workout", test_data, user_id="default")
        print("✓ Projection set: current_workout")
        
        # Get projection
        retrieved = get_projection("current_workout", user_id="default")
        print(f"✓ Projection retrieved: {retrieved is not None}")
        
        if retrieved:
            print(f"  Data: {list(retrieved.keys())}")
    
    except Exception as e:
        print(f"✗ Projection operations failed: {e}")
        return False
    
    print()
    return True


def test_exercises():
    """Test exercise operations."""
    print("=" * 60)
    print("EXERCISE OPERATIONS TEST")
    print("=" * 60)
    
    try:
        # Load default exercises
        load_default_exercises("default")
        print("✓ Default exercises loaded")
        
        # Get exercises
        exercises = get_exercises(user_id="default")
        print(f"✓ Retrieved {len(exercises)} exercises")
        
        if exercises:
            categories = set(ex.get("category") for ex in exercises if ex.get("category"))
            print(f"  Categories: {', '.join(sorted(categories))}")
            print(f"  Sample: {exercises[0]['name']} ({exercises[0]['category']})")
    
    except Exception as e:
        print(f"✗ Exercise operations failed: {e}")
        return False
    
    print()
    return True


def run_all_tests():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "GYM APP DATABASE TESTS" + " " * 21 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    test_connection()
    
    results = []
    results.append(("Table Initialization", test_tables()))
    results.append(("Event Operations", test_events()))
    results.append(("Projection Operations", test_projections()))
    results.append(("Exercise Operations", test_exercises()))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:>8} | {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! Database is working correctly.")
        return 0
    else:
        print("✗ Some tests failed. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())



