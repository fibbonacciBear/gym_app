# Production Architecture

This document outlines the production deployment architecture for the Voice Workout Tracker.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS CloudFront                              │
│                         (CDN / Edge)                                │
├─────────────────────────────┬───────────────────────────────────────┤
│     Static Assets           │          API Routes                   │
│     (S3 Origin)             │     (API Gateway Origin)              │
│                             │                                       │
│  /index.html                │  /api/* → API Gateway → Lambda        │
│  /css/*                     │                                       │
│  /js/*                      │                                       │
│  /data/exercises.json       │                                       │
└─────────────────────────────┴───────────────┬───────────────────────┘
                                              │
                                              ▼
                               ┌──────────────────────────┐
                               │      AWS Lambda          │
                               │   (Python + FastAPI)     │
                               │                          │
                               │  Runtime: Python 3.11    │
                               │  Handler: Mangum         │
                               │  Memory: 512MB           │
                               │  Timeout: 30s            │
                               └────────────┬─────────────┘
                                            │
                                            ▼
                               ┌──────────────────────────┐
                               │         Neon             │
                               │   (Serverless Postgres)  │
                               │                          │
                               │  - Connection pooling    │
                               │  - Auto-suspend          │
                               │  - Branching for dev     │
                               └──────────────────────────┘
```

---

## Components

### 1. AWS CloudFront

**Purpose:** Global CDN for low-latency content delivery and unified domain.

**Configuration:**
- **Distribution:** Single distribution with multiple origins
- **SSL:** AWS Certificate Manager (ACM) for HTTPS
- **Caching:** Static assets cached at edge, API requests pass-through

**Behaviors:**

| Path Pattern | Origin | Cache Policy | Notes |
|--------------|--------|--------------|-------|
| `/api/*` | API Gateway | Disabled (pass-through) | All API requests |
| `/data/*` | S3 | 24 hours | Exercise data (JSON) |
| `/*` (default) | S3 | 1 hour | HTML, CSS, JS |

**Headers:**
- Forward `Authorization` header to API Gateway
- Add `X-Forwarded-For` for client IP tracking

---

### 2. AWS S3 (Static Assets)

**Purpose:** Host frontend static files.

**Bucket Structure:**
```
s3://gym-app-frontend-{env}/
├── index.html
├── css/
│   └── styles.css
├── js/
│   ├── api.js
│   └── app.js
└── data/
    └── exercises.json
```

**Configuration:**
- Private bucket (no public access)
- CloudFront Origin Access Control (OAC) for secure access
- Versioning enabled for rollback capability

---

### 3. AWS API Gateway

**Purpose:** HTTP API endpoint for Lambda integration.

**Configuration:**
- **Type:** HTTP API (v2) - lower latency, lower cost than REST API
- **Routes:** `ANY /api/{proxy+}` → Lambda
- **CORS:** Handled by FastAPI (not API Gateway)
- **Throttling:** 1000 requests/second (adjustable)

---

### 4. AWS Lambda

**Purpose:** Run FastAPI backend application.

**Configuration:**

| Setting | Value |
|---------|-------|
| Runtime | Python 3.11 |
| Handler | `lambda_handler.handler` |
| Memory | 512 MB |
| Timeout | 30 seconds |
| Architecture | arm64 (Graviton2 - cost effective) |

**Environment Variables:**
```
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/gymdb?sslmode=require
ENVIRONMENT=production
LOG_LEVEL=INFO
```

**Lambda Adapter (Mangum):**
```python
# lambda_handler.py
from mangum import Mangum
from backend.main import app

handler = Mangum(app, lifespan="off")
```

**Deployment Package:**
- Use Lambda Layers for dependencies (reduces cold start)
- Or: Container image for larger dependencies

---

### 5. Neon (Serverless Postgres)

**Purpose:** Managed PostgreSQL database with serverless scaling.

**Why Neon:**
- ✅ Serverless - scales to zero when inactive
- ✅ Connection pooling built-in (critical for Lambda)
- ✅ Postgres-compatible (easy SQLite migration)
- ✅ Branching for development/staging environments
- ✅ Generous free tier

**Configuration:**

| Setting | Value |
|---------|-------|
| Region | us-east-1 (same as Lambda) |
| Compute | 0.25 - 2 CU (auto-scaling) |
| Storage | Starts at 0, scales as needed |
| Pooling | Enabled (PgBouncer) |

**Connection String Format:**
```
postgresql://user:password@ep-xxxx-xxxx.us-east-1.aws.neon.tech/gymdb?sslmode=require
```

**Branching Strategy:**
- `main` → Production
- `staging` → Staging environment
- `dev-{feature}` → Feature development branches

---

## Database Schema (Postgres)

Migration from SQLite to Postgres:

```sql
-- Events table (event sourcing)
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_workout_id ON events((data->>'workout_id'));

-- Optional: Materialized view for workout summaries
CREATE MATERIALIZED VIEW workout_summaries AS
SELECT 
    data->>'workout_id' as workout_id,
    MIN(timestamp) as started_at,
    MAX(timestamp) as last_updated,
    COUNT(*) FILTER (WHERE event_type = 'set_logged') as total_sets
FROM events
WHERE data->>'workout_id' IS NOT NULL
GROUP BY data->>'workout_id';
```

---

## Environments

| Environment | CloudFront | Lambda | Neon Branch | Purpose |
|-------------|------------|--------|-------------|---------|
| Production | `gym.example.com` | `gym-app-prod` | `main` | Live users |
| Staging | `staging.gym.example.com` | `gym-app-staging` | `staging` | Pre-release testing |
| Development | Local | Local | `dev-*` | Feature development |

---

## Deployment Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   GitHub    │────▶│  GitHub     │────▶│   Build &   │────▶│   Deploy    │
│   Push      │     │  Actions    │     │   Test      │     │   to AWS    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │  - Lint/Test    │
                                    │  - Build Lambda │
                                    │  - Upload to S3 │
                                    │  - Update Lambda│
                                    │  - Invalidate   │
                                    │    CloudFront   │
                                    └─────────────────┘
```

**Deployment Steps:**

1. **Frontend:** Sync to S3, invalidate CloudFront cache
2. **Backend:** Update Lambda function code
3. **Database:** Run migrations via CI (if schema changes)

---

## Security

### Secrets Management

| Secret | Storage | Access |
|--------|---------|--------|
| `DATABASE_URL` | AWS Secrets Manager | Lambda IAM role |
| Neon credentials | AWS Secrets Manager | Lambda IAM role |
| API keys (future) | AWS Secrets Manager | Lambda IAM role |

### IAM Roles

**Lambda Execution Role:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:gym-app/*"
    }
  ]
}
```

### Network Security

- Neon: SSL required (`sslmode=require`)
- CloudFront: HTTPS only, redirect HTTP
- API Gateway: No direct public access (CloudFront only)

---

## Monitoring & Observability

### CloudWatch

- **Lambda Logs:** All application logs
- **Lambda Metrics:** Invocations, duration, errors, cold starts
- **API Gateway:** Request count, latency, 4xx/5xx errors

### Alarms

| Metric | Threshold | Action |
|--------|-----------|--------|
| Lambda Errors | > 5% | SNS notification |
| Lambda Duration | > 10s avg | SNS notification |
| API 5xx Rate | > 1% | SNS notification |

### Neon Dashboard

- Query performance
- Connection count
- Storage usage

---

## Cost Estimate (Monthly)

### Free Tier (First 12 months / Low usage)

| Component | Free Tier | Estimated Usage |
|-----------|-----------|-----------------|
| CloudFront | 1 TB transfer | < 10 GB |
| S3 | 5 GB storage | < 100 MB |
| Lambda | 1M requests, 400K GB-s | < 100K requests |
| API Gateway | 1M requests | < 100K requests |
| Neon | 0.5 GB, 100 compute-hours | < 0.5 GB |

**Estimated cost:** $0 - $5/month for hobby use

### Growth Scenario (1000 active users)

| Component | Usage | Cost |
|-----------|-------|------|
| CloudFront | 50 GB | ~$5 |
| Lambda | 500K requests | ~$0.10 |
| API Gateway | 500K requests | ~$0.50 |
| Neon | Pro plan | $19 |

**Estimated cost:** ~$25/month

---

## Local Development

To run locally with production-like setup:

```bash
# Start backend with SQLite (default)
cd backend
uvicorn main:app --reload --port 8000

# Or connect to Neon dev branch
export DATABASE_URL="postgresql://...@ep-xxx.neon.tech/gymdb_dev"
uvicorn main:app --reload --port 8000

# Frontend: serve static files
cd frontend
python -m http.server 3000
```

---

## Future Considerations

- [ ] **Custom domain:** Configure Route 53 + ACM certificate
- [ ] **WAF:** Add AWS WAF for rate limiting and security rules
- [ ] **Multi-region:** Neon read replicas for global latency
- [ ] **Caching:** Redis/ElastiCache for session data or hot queries
- [ ] **CI/CD:** Full GitHub Actions or AWS CodePipeline setup

---

*Last updated: December 2024*







