# PostgreSQL Quick Start Guide

## 🎯 Goal
Test your app locally with PostgreSQL before deploying to AWS.

## ✅ Prerequisites

- Docker installed and running
- Conda environment activated: `conda activate gym_app`
- Dependencies installed (including `psycopg2-binary`)

## 🚀 Quick Start (5 steps)

### 1. Start PostgreSQL Container

```bash
docker-compose up -d
```

This starts PostgreSQL 16 on port 5432 with:
- Database: `gym_app`
- User: `gymuser`
- Password: `gympass123`
- Auto-initialized tables

### 2. Configure Environment

```bash
# Create .env file from example (if you haven't)
cp .env.example .env

# Edit .env and set DATABASE_URL
echo "DATABASE_URL=postgresql://gymuser:gympass123@localhost:5432/gym_app" >> .env
```

Or manually edit `.env` and add/uncomment:
```
DATABASE_URL=postgresql://gymuser:gympass123@localhost:5432/gym_app
```

### 3. Test Database Connection

```bash
python scripts/test_database.py
```

You should see:
```
✓ Using PostgreSQL
✓ Database initialized successfully
✓ Event appended
✓ Projection set
✓ Retrieved 29 exercises
✓ All tests passed!
```

### 4. Start Application

```bash
uvicorn backend.main:app --reload --port 8000
```

The app will now use PostgreSQL instead of SQLite!

### 5. Test in Browser

Open http://localhost:8000 and log some workouts. All data is now stored in PostgreSQL.

## 🔍 Verify PostgreSQL is Being Used

Check the terminal output when starting the app. You should see database connection info.

Or query the database directly:

```bash
docker exec -it gym_app_postgres psql -U gymuser -d gym_app -c "SELECT COUNT(*) FROM events;"
```

## 🛑 Stop PostgreSQL

```bash
# Stop container (keeps data)
docker-compose stop

# Stop and remove container (keeps data in volume)
docker-compose down

# Remove everything including data (fresh start)
docker-compose down -v
```

## 🔄 Switch Back to SQLite

```bash
# Edit .env and remove/comment out DATABASE_URL
# DATABASE_URL=

# Or delete the line entirely
```

Restart the app and it will use SQLite again.

## 📚 Learn More

- Detailed PostgreSQL guide: [infrastructure/LOCAL_POSTGRES_SETUP.md](infrastructure/LOCAL_POSTGRES_SETUP.md)
- AWS deployment guide: [infrastructure/DEPLOYMENT.md](infrastructure/DEPLOYMENT.md)

## 🐛 Common Issues

### Container won't start

```bash
# Check if port 5432 is already in use
lsof -i :5432

# View container logs
docker-compose logs postgres
```

### Connection refused

```bash
# Wait for container to be healthy (10-15 seconds)
docker-compose ps

# Check health
docker exec gym_app_postgres pg_isready -U gymuser
```

### Permission errors

```bash
# Restart with fresh state
docker-compose down -v
docker-compose up -d
```

---

## 🎉 Ready for AWS Deployment!

Once you've tested locally with PostgreSQL and everything works, you're ready to deploy to AWS!

See [infrastructure/DEPLOYMENT.md](infrastructure/DEPLOYMENT.md) for AWS deployment instructions.



