-- PostgreSQL initialization script for gym_app
-- This script creates the necessary tables for the event-sourced workout tracker

-- Events table (append-only event log)
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_user_id ON events(user_id);
CREATE INDEX idx_events_event_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_payload ON events USING GIN(payload);

-- Projections table (derived state from events)
CREATE TABLE IF NOT EXISTS projections (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, key)
);

CREATE INDEX idx_projections_user_id ON projections(user_id);
CREATE INDEX idx_projections_key ON projections(key);
CREATE INDEX idx_projections_value ON projections USING GIN(value);

-- Exercises table (reference data)
CREATE TABLE IF NOT EXISTS exercises (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    exercise_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    is_custom BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, exercise_id)
);

CREATE INDEX idx_exercises_user_id ON exercises(user_id);
CREATE INDEX idx_exercises_category ON exercises(category);

-- Comments for documentation
COMMENT ON TABLE events IS 'Append-only event log for event sourcing pattern';
COMMENT ON TABLE projections IS 'Materialized views/projections derived from events';
COMMENT ON TABLE exercises IS 'Reference data for available exercises';

COMMENT ON COLUMN events.event_id IS 'Unique identifier for the event (UUID)';
COMMENT ON COLUMN events.user_id IS 'User who generated the event';
COMMENT ON COLUMN events.event_type IS 'Type of event (e.g., WorkoutStarted, SetLogged)';
COMMENT ON COLUMN events.payload IS 'Event data in JSONB format';
COMMENT ON COLUMN events.timestamp IS 'When the event occurred';

COMMENT ON COLUMN projections.key IS 'Projection identifier (e.g., current_workout, workout_history)';
COMMENT ON COLUMN projections.value IS 'Projection data in JSONB format';

-- Grant permissions (for RDS, these are handled by IAM, but useful for local dev)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gymuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gymuser;

