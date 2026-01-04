# Local PostgreSQL Setup Guide

This guide helps you set up a local PostgreSQL instance for development and testing before AWS deployment.

## Why Use PostgreSQL Locally?

- **Production Parity**: Test with the same database engine AWS will use
- **Catch Issues Early**: Find PostgreSQL-specific bugs before deployment
- **Migration Testing**: Test SQLite→PostgreSQL migration
- **Performance Testing**: Benchmark queries with realistic data

## Quick Start with Docker Compose

### 1. Start PostgreSQL

```bash
# Start PostgreSQL container in background
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs postgres
```

The container will:
- Run PostgreSQL 16 on port 5432
- Create database `gym_app`
- Create user `gymuser` with password `gympass123`
- Initialize tables automatically using `init_db.sql`
- Persist data in a Docker volume

### 2. Configure Application

```bash
# Copy example environment file if you haven't already
cp .env.example .env

# Edit .env and set DATABASE_URL
DATABASE_URL=postgresql://gymuser:gympass123@localhost:5432/gym_app
```

### 3. Install PostgreSQL Dependencies

```bash
# If using conda
conda env update -f environment.yml
conda activate gym_app

# Or if using pip
pip install psycopg2-binary==2.9.9
```

### 4. Run Application

```bash
# Start the app - it will automatically use PostgreSQL
uvicorn backend.main:app --reload --port 8000
```

### 5. Stop PostgreSQL

```bash
# Stop container (preserves data)
docker-compose stop

# Stop and remove container (preserves data in volume)
docker-compose down

# Stop and remove ALL data (fresh start)
docker-compose down -v
```

## Manual PostgreSQL Commands

### Connect to Database

```bash
# Using psql (PostgreSQL client)
docker exec -it gym_app_postgres psql -U gymuser -d gym_app

# Or connect from host (if psql installed)
psql -h localhost -U gymuser -d gym_app
```

### Useful SQL Commands

```sql
-- List all tables
\dt

-- Describe a table
\d events

-- Count events
SELECT COUNT(*) FROM events;

-- View recent events
SELECT event_id, event_type, timestamp 
FROM events 
ORDER BY timestamp DESC 
LIMIT 10;

-- View all projections
SELECT user_id, key, updated_at 
FROM projections;

-- Check exercises
SELECT exercise_id, name, category 
FROM exercises 
WHERE user_id = 'default'
ORDER BY name;

-- Exit psql
\q
```

## Switching Between SQLite and PostgreSQL

The app automatically detects which database to use based on `DATABASE_URL`:

### Use SQLite (Simple Local Dev)
```bash
# In .env file:
DATABASE_URL=
# (empty or commented out)
```

### Use PostgreSQL (Production-like Testing)
```bash
# In .env file:
DATABASE_URL=postgresql://gymuser:gympass123@localhost:5432/gym_app
```

No code changes needed! The backend automatically uses the correct database adapter.

## Database Features

### Event Sourcing Tables

| Table | Purpose | Notes |
|-------|---------|-------|
| `events` | Append-only event log | Primary source of truth |
| `projections` | Derived state/views | Computed from events |
| `exercises` | Exercise library | Reference data |

### PostgreSQL-Specific Features

- **JSONB columns**: Native JSON support with indexing
- **GIN indexes**: Fast JSONB queries
- **Transactions**: Full ACID compliance
- **Connection pooling**: Ready for RDS Proxy

### Indexes Created

- `events`: user_id, event_type, timestamp, payload (GIN)
- `projections`: user_id, key, value (GIN)
- `exercises`: user_id, category

## Migrating SQLite Data to PostgreSQL

If you have existing SQLite data you want to migrate:

```bash
# 1. Export events from SQLite (manual script needed)
# 2. Import to PostgreSQL
# 3. Replay events to rebuild projections
```

*Note: A migration script can be added if needed.*

## Troubleshooting

### Connection Refused

```bash
# Check if container is running
docker-compose ps

# Restart container
docker-compose restart postgres

# View logs
docker-compose logs postgres
```

### Permission Denied

```bash
# Reset permissions
docker-compose down -v
docker-compose up -d
```

### Port Already in Use

If port 5432 is already taken:

1. Stop other PostgreSQL instances
2. Or edit `docker-compose.yml` to use a different port:
   ```yaml
   ports:
     - "5433:5432"  # Use 5433 on host
   ```
3. Update `DATABASE_URL` to match:
   ```
   DATABASE_URL=postgresql://gymuser:gympass123@localhost:5433/gym_app
   ```

### Table Already Exists Errors

```bash
# Drop and recreate database
docker exec -it gym_app_postgres psql -U gymuser -d postgres -c "DROP DATABASE gym_app;"
docker exec -it gym_app_postgres psql -U gymuser -d postgres -c "CREATE DATABASE gym_app;"
docker-compose restart postgres
```

## Performance Testing

### Generate Load

```python
# Example: Log 1000 sets to test performance
import requests

for i in range(1000):
    requests.post("http://localhost:8000/api/events", json={
        "event_type": "SetLogged",
        "payload": {
            "workout_id": "test-workout",
            "exercise_id": "bench-press",
            "weight": 185 + (i % 20),
            "reps": 8 + (i % 5),
            "unit": "kg"
        }
    })
```

### Query Performance

```sql
-- Explain query plan
EXPLAIN ANALYZE 
SELECT * FROM events 
WHERE user_id = 'default' 
  AND event_type = 'SetLogged'
ORDER BY timestamp DESC 
LIMIT 100;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan 
FROM pg_stat_user_indexes 
ORDER BY idx_scan DESC;
```

## Production Comparison

| Feature | Local PostgreSQL | AWS RDS |
|---------|-----------------|---------|
| Engine | PostgreSQL 16 | PostgreSQL 16 |
| Connection | Direct | Via RDS Proxy |
| Backups | Manual | Automated (3-tier) |
| Scaling | Single instance | Multi-AZ, Read replicas |
| Monitoring | Logs only | CloudWatch metrics |

## Next Steps

1. ✅ Test app with PostgreSQL locally
2. ✅ Verify all events and projections work
3. ✅ Run performance benchmarks
4. 🚀 Deploy to AWS with confidence!

---

For AWS deployment, see [DEPLOYMENT.md](DEPLOYMENT.md)



