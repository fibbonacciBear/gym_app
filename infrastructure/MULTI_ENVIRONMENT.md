# Multi-Environment Deployment Guide

## Environment Strategy

### Production
- **Domain:** titantrakr.com
- **Database:** RDS t4g.micro (always-on)
- **Backups:** 30-day automated + AWS Backup tiers
- **Stack name:** `gym-app-prod`

### Staging
- **Domain:** staging.titantrakr.com
- **Database:** RDS t4g.micro (can stop when not testing)
- **Backups:** 7-day automated only (cheaper)
- **Stack name:** `gym-app-staging`

### Development (Optional)
- **Local only** - Use SQLite, no AWS deployment
- **Or:** Lightweight stack with Function URL only (no custom domain)

---

## Deployment Workflow

```
Code Changes → Git Push → Deploy to Staging → Test → Deploy to Prod
```

---

## Step-by-Step: Deploy Both Environments

### 1. Create Staging DNS Record

```bash
# Add staging subdomain to titantrakr.com hosted zone
aws route53 change-resource-record-sets \
  --hosted-zone-id Z062771734T6PR83RBVON \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "staging.titantrakr.com",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "CLOUDFRONT_DOMAIN_HERE"}]
      }
    }]
  }'
```

### 2. Deploy Staging Environment First

```bash
# Build and push staging Docker image
docker build -t gym-app:staging -f infrastructure/Dockerfile .
aws ecr get-login-password --region us-west-1 | \
  docker login --username AWS --password-stdin \
  273354662815.dkr.ecr.us-west-1.amazonaws.com

docker tag gym-app:staging \
  273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:staging
docker push 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:staging

# Deploy staging stack
aws cloudformation create-stack \
  --stack-name gym-app-staging \
  --template-body file://infrastructure/cloudformation-simple.yaml \
  --parameters file://infrastructure/deploy-parameters-staging.json \
  --capabilities CAPABILITY_IAM \
  --region us-west-1

# Wait for completion (~15 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name gym-app-staging \
  --region us-west-1
```

### 3. Test Staging

```bash
# Get staging URL
STAGING_URL=$(aws cloudformation describe-stacks \
  --stack-name gym-app-staging \
  --region us-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`PrimaryDomainURL`].OutputValue' \
  --output text)

# Test health endpoint
curl $STAGING_URL/api/health

# Test in browser
open $STAGING_URL
```

### 4. Deploy Production (After Staging Verified)

```bash
# Build and push prod Docker image
docker build -t gym-app:prod -f infrastructure/Dockerfile .
docker tag gym-app:prod \
  273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod
docker push 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod

# Deploy prod stack
aws cloudformation create-stack \
  --stack-name gym-app-prod \
  --template-body file://infrastructure/cloudformation-simple.yaml \
  --parameters file://infrastructure/deploy-parameters.json \
  --capabilities CAPABILITY_IAM \
  --region us-west-1

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name gym-app-prod \
  --region us-west-1
```

---

## Environment Comparison

| Component | Staging | Production |
|-----------|---------|------------|
| **Domain** | staging.titantrakr.com | titantrakr.com |
| **Database** | t4g.micro (stop when idle) | t4g.micro (always-on) |
| **Backup Retention** | 7 days | 30 days + AWS Backup |
| **Lambda Memory** | 512 MB | 512 MB (same) |
| **CloudFront** | Yes | Yes |
| **SSL Cert** | Wildcard *.titantrakr.com | Multi-domain cert |
| **Cost** | ~$15/month (stop DB off-hours) | ~$30/month |

---

## Promotion Process (Staging → Prod)

### Option A: Docker Image Promotion (Recommended)

```bash
# 1. Test staging thoroughly
# 2. Retag staging image as prod
aws ecr batch-get-image \
  --repository-name gym-app \
  --image-ids imageTag=staging \
  --region us-west-1 \
  --query 'images[0].imageManifest' \
  --output text | \
aws ecr put-image \
  --repository-name gym-app \
  --image-tag prod \
  --image-manifest file:///dev/stdin \
  --region us-west-1

# 3. Update prod Lambda
aws lambda update-function-code \
  --function-name prod-gym-app \
  --image-uri 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod \
  --region us-west-1

# 4. Verify
curl https://titantrakr.com/api/health
```

### Option B: Blue/Green Deployment

```bash
# 1. Deploy new "green" stack
aws cloudformation create-stack \
  --stack-name gym-app-prod-green \
  --template-body file://infrastructure/cloudformation-simple.yaml \
  --parameters file://infrastructure/deploy-parameters.json

# 2. Test green environment
# 3. Swap Route53 DNS to point to green CloudFront
# 4. Monitor
# 5. Delete blue stack if successful
```

---

## Environment-Specific Features

### Staging Optimizations

#### Stop Database Overnight (Save ~60% on DB costs)

```bash
# Stop staging DB at 10 PM PST (6 AM UTC)
aws rds stop-db-instance \
  --db-instance-identifier staging-gym-app-db \
  --region us-west-1

# Start staging DB at 8 AM PST (4 PM UTC)
aws rds start-db-instance \
  --db-instance-identifier staging-gym-app-db \
  --region us-west-1
```

**Automate with EventBridge (CloudWatch Events):**

```yaml
# Add to CloudFormation for staging
StopDBSchedule:
  Type: AWS::Events::Rule
  Condition: IsStaging
  Properties:
    ScheduleExpression: 'cron(0 6 * * ? *)'  # 6 AM UTC = 10 PM PST
    Targets:
      - Arn: !GetAtt StopDBLambda.Arn
        Id: StopDB

StartDBSchedule:
  Type: AWS::Events::Rule
  Condition: IsStaging
  Properties:
    ScheduleExpression: 'cron(0 16 * * ? *)'  # 4 PM UTC = 8 AM PST
    Targets:
      - Arn: !GetAtt StartDBLambda.Arn
        Id: StartDB
```

---

## Configuration Differences

### backend/config.py (Environment Detection)

```python
# Detect environment from Lambda
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
IS_PRODUCTION = ENVIRONMENT == "prod"
IS_STAGING = ENVIRONMENT == "staging"

# Different log levels per environment
if IS_PRODUCTION:
    LOG_LEVEL = "WARNING"
elif IS_STAGING:
    LOG_LEVEL = "INFO"
else:
    LOG_LEVEL = "DEBUG"
```

### Staging-Specific Settings

```python
# In staging, enable debug features
if IS_STAGING:
    # Show detailed error messages
    app.debug = True
    # Allow CORS from localhost (for local frontend dev)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"]
    )
```

---

## Cost Optimization for Staging

### Current Staging Cost: ~$15/month

| Component | Optimization | Savings |
|-----------|--------------|---------|
| **RDS** | Stop off-hours (14 hours/day) | Save $7/month |
| **RDS Proxy** | Remove (not needed for staging) | Save $11/month |
| **Lambda** | Use ARM64 (Graviton2) | Save 20% |
| **CloudFront** | Use PriceClass_100 | Minimal data = minimal cost |

**Optimized Staging Cost: ~$5-8/month**

### Remove RDS Proxy from Staging

Lambda can connect directly to RDS (fewer concurrent users):

```yaml
# In template, make RDS Proxy conditional
RDSProxy:
  Type: AWS::RDS::DBProxy
  Condition: IsProduction  # Only create for prod
  Properties:
    ...
```

---

## Database Strategy

### Separate Databases (Current Approach)

**Pros:**
- ✅ Complete isolation
- ✅ Can test migrations safely
- ✅ Staging can have different schema versions

**Cons:**
- ❌ More expensive (2x RDS cost)
- ❌ Need to sync test data manually

### Shared Database with Schemas (Alternative)

**One RDS instance, two PostgreSQL schemas:**

```sql
-- Staging schema
CREATE SCHEMA staging;
-- Production schema  
CREATE SCHEMA prod;
```

**Pros:**
- ✅ Cheaper (1x RDS cost)
- ✅ Easier to clone prod data → staging

**Cons:**
- ❌ Risk of cross-contamination
- ❌ Staging load affects prod

**Recommendation:** Keep separate for safety, optimize staging with stop/start schedule.

---

## Deployment Commands Cheat Sheet

### Deploy Staging

```bash
cd /Users/akashganesan/Documents/code/gym_app

# Build & push
./infrastructure/scripts/build-and-push.sh staging

# Deploy stack
aws cloudformation create-stack \
  --stack-name gym-app-staging \
  --template-body file://infrastructure/cloudformation-simple.yaml \
  --parameters file://infrastructure/deploy-parameters-staging.json \
  --capabilities CAPABILITY_IAM \
  --region us-west-1
```

### Deploy Production

```bash
# Build & push
./infrastructure/scripts/build-and-push.sh prod

# Deploy stack
aws cloudformation create-stack \
  --stack-name gym-app-prod \
  --template-body file://infrastructure/cloudformation-simple.yaml \
  --parameters file://infrastructure/deploy-parameters.json \
  --capabilities CAPABILITY_IAM \
  --region us-west-1
```

### Update Staging (After Code Changes)

```bash
# Build new image
./infrastructure/scripts/build-and-push.sh staging

# Update Lambda only (fast)
aws lambda update-function-code \
  --function-name staging-gym-app \
  --image-uri 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:staging \
  --region us-west-1
```

### Update Production (After Staging Verified)

```bash
# Promote staging image to prod tag
aws ecr batch-get-image \
  --repository-name gym-app \
  --image-ids imageTag=staging \
  --query 'images[].imageManifest' \
  --output text | \
aws ecr put-image \
  --repository-name gym-app \
  --image-tag prod \
  --image-manifest file:///dev/stdin

# Update prod Lambda
aws lambda update-function-code \
  --function-name prod-gym-app \
  --image-uri 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod \
  --region us-west-1
```

---

## Environment URLs

| Environment | URL | Purpose |
|-------------|-----|---------|
| **Local** | http://localhost:8000 | Development |
| **Staging** | https://staging.titantrakr.com | Testing |
| **Production** | https://titantrakr.com | Live users |
| **Production (www)** | https://www.titantrakr.com | Alias to main |

---

## Data Management

### Copy Production Data to Staging (for Testing)

```bash
# 1. Create snapshot of prod DB
aws rds create-db-snapshot \
  --db-instance-identifier prod-gym-app-db \
  --db-snapshot-identifier prod-snapshot-$(date +%Y%m%d) \
  --region us-west-1

# 2. Restore snapshot to staging
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier staging-gym-app-db-new \
  --db-snapshot-identifier prod-snapshot-$(date +%Y%m%d) \
  --db-instance-class db.t4g.micro \
  --region us-west-1

# 3. Update staging RDS Proxy to point to new DB
# 4. Delete old staging DB
```

### Anonymize Staging Data (Privacy)

```sql
-- After restoring prod data to staging, anonymize it
UPDATE projections 
SET data = jsonb_set(
  data::jsonb, 
  '{email}', 
  '"test+user@example.com"'::jsonb
)
WHERE key LIKE 'user_profile:%';
```

---

## Monitoring Per Environment

### CloudWatch Dashboard

Create environment-specific dashboards:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name gym-app-staging \
  --dashboard-body file://dashboards/staging-dashboard.json

aws cloudwatch put-dashboard \
  --dashboard-name gym-app-prod \
  --dashboard-body file://dashboards/prod-dashboard.json
```

### Alarms

**Staging:** Minimal alarms (Lambda errors only)  
**Production:** Full alarm suite:
- Lambda errors > 5/minute
- RDS CPU > 80%
- RDS disk space < 20%
- CloudFront 5xx errors > 1%
- Backup job failures

---

## Cost Breakdown

### Monthly Costs

| Component | Staging | Production |
|-----------|---------|------------|
| RDS PostgreSQL | $12 → $5 (with stop schedule) | $12 |
| RDS Proxy | $0 (removed) | $11 |
| Lambda | $0 (free tier) | $0 (free tier) |
| CloudFront | ~$1 | ~$5 |
| AWS Backup | $0 (RDS only) | ~$2 |
| Route53 | Shared | $1.50 |
| **Total** | **~$6/month** | **~$31.50/month** |

**Both environments: ~$37.50/month**

---

## Quick Deploy Script

Create `infrastructure/scripts/deploy.sh`:

```bash
#!/bin/bash
set -e

ENVIRONMENT=$1  # prod or staging

if [ "$ENVIRONMENT" != "prod" ] && [ "$ENVIRONMENT" != "staging" ]; then
  echo "Usage: ./deploy.sh [prod|staging]"
  exit 1
fi

echo "🚀 Deploying to $ENVIRONMENT..."

# 1. Build Docker image
echo "📦 Building Docker image..."
docker build -t gym-app:$ENVIRONMENT -f infrastructure/Dockerfile .

# 2. Push to ECR
echo "☁️ Pushing to ECR..."
aws ecr get-login-password --region us-west-1 | \
  docker login --username AWS --password-stdin \
  273354662815.dkr.ecr.us-west-1.amazonaws.com

docker tag gym-app:$ENVIRONMENT \
  273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:$ENVIRONMENT
docker push 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:$ENVIRONMENT

# 3. Check if stack exists
STACK_EXISTS=$(aws cloudformation describe-stacks \
  --stack-name gym-app-$ENVIRONMENT \
  --region us-west-1 2>/dev/null || echo "false")

if [ "$STACK_EXISTS" = "false" ]; then
  # Create new stack
  echo "🆕 Creating new stack..."
  aws cloudformation create-stack \
    --stack-name gym-app-$ENVIRONMENT \
    --template-body file://infrastructure/cloudformation-simple.yaml \
    --parameters file://infrastructure/deploy-parameters-$ENVIRONMENT.json \
    --capabilities CAPABILITY_IAM \
    --region us-west-1
  
  echo "⏳ Waiting for stack creation (15-20 minutes)..."
  aws cloudformation wait stack-create-complete \
    --stack-name gym-app-$ENVIRONMENT \
    --region us-west-1
else
  # Update Lambda function code only (fast)
  echo "🔄 Updating existing Lambda..."
  aws lambda update-function-code \
    --function-name $ENVIRONMENT-gym-app \
    --image-uri 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:$ENVIRONMENT \
    --region us-west-1
  
  aws lambda wait function-updated \
    --function-name $ENVIRONMENT-gym-app \
    --region us-west-1
fi

# 4. Get URL
URL=$(aws cloudformation describe-stacks \
  --stack-name gym-app-$ENVIRONMENT \
  --region us-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`PrimaryDomainURL`].OutputValue' \
  --output text)

echo "✅ Deployment complete!"
echo "🌐 URL: $URL"
echo "🏥 Health: $URL/api/health"
```

Make it executable:
```bash
chmod +x infrastructure/scripts/deploy.sh
```

Usage:
```bash
./deploy-staging.sh
./deploy-production.sh
```

---

## SSL Certificate Note

**Important:** The CloudFormation template creates a **wildcard certificate** for staging:
- `*.titantrakr.com` covers `staging.titantrakr.com`

For production, it creates a multi-domain certificate:
- `titantrakr.com`
- `www.titantrakr.com`

Both use DNS validation (automatic if Route53 manages your domains).

---

## Rollback Procedures

### Rollback Staging

```bash
# Just redeploy previous image
aws lambda update-function-code \
  --function-name staging-gym-app \
  --image-uri 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:staging-previous \
  --region us-west-1
```

### Rollback Production

```bash
# Option 1: Quick rollback (previous Lambda image)
aws lambda update-function-code \
  --function-name prod-gym-app \
  --publish-version \
  --region us-west-1

aws lambda update-alias \
  --function-name prod-gym-app \
  --name live \
  --function-version <PREVIOUS_VERSION> \
  --region us-west-1

# Option 2: Database rollback (if schema changed)
# Restore from backup (see BACKUP_STRATEGY.md)
```

---

## Next Steps

1. ✅ CloudFormation template supports both environments
2. ✅ Staging uses `staging.titantrakr.com`
3. ✅ Production uses titantrakr.com
4. ✅ Separate databases for isolation
5. ✅ Cost-optimized staging (can stop DB off-hours)

**Ready to deploy!**

Run:
```bash
# Deploy staging first
./deploy-staging.sh

# Then production
./deploy-production.sh
```



