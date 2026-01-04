# Deployment Guide - Manual Control

## Overview

This project uses **manual deployment** - you control when code is deployed to AWS. Pushing to git does NOT trigger automatic deployments.

---

## Quick Commands

### Deploy to Staging
```bash
make deploy-staging
```

### Deploy to Production
```bash
make deploy-prod
# (asks for confirmation before deploying)
```

### Test Locally
```bash
make test-local
# Opens http://localhost:8000
```

---

## Full Workflow

### 1. Development (Local)
```bash
# Make code changes
vim backend/main.py

# Test locally
make test-local
# Visit http://localhost:8000

# Commit to git (optional - does NOT deploy!)
git add .
git commit -m "Add new feature"
git push origin main
```

### 2. Deploy to Staging
```bash
# When ready to test on AWS
make deploy-staging

# What it does:
# 1. Builds Docker image
# 2. Pushes to AWS ECR
# 3. Updates Lambda function
# 4. Tests /api/health endpoint
# Time: ~2-3 minutes
```

**Test staging:** https://staging.titantrakr.com

### 3. Deploy to Production
```bash
# After staging verified
make deploy-prod

# Asks: "Are you sure? (yes/no)"
# Type: yes

# Same process as staging, but for production
```

**Test production:** https://titantrakr.com

---

## Alternative Commands

If `make` isn't available, use the scripts directly:

```bash
# Deploy to staging
./infrastructure/scripts/deploy.sh staging

# Deploy to production
./infrastructure/scripts/deploy.sh prod

# Quick deploy with confirmation
./deploy-quick.sh prod
```

---

## What Happens During Deployment

```
1. 📦 Build Docker Image
   ├─ Copies your code into container
   ├─ Installs dependencies (requirements.txt)
   └─ Creates image: gym-app:staging

2. ☁️  Push to AWS ECR
   ├─ Logs into AWS container registry
   └─ Uploads image (~300MB, takes 30-60 sec)

3. ⚡ Update Lambda Function
   ├─ Points Lambda to new image
   ├─ Lambda pulls image from ECR
   └─ New code is live (~30 sec)

4. 🏥 Health Check
   └─ Confirms /api/health returns 200 OK
```

---

## Deployment Checklist

### Before Deploying to Staging:
- [ ] Code works locally (`make test-local`)
- [ ] No obvious bugs
- [ ] Commit changes to git (optional)

### Before Deploying to Production:
- [ ] Staging deployed and tested
- [ ] Key features verified on staging
- [ ] No errors in staging logs
- [ ] Database migrations tested (if any)

---

## Rollback (If Something Goes Wrong)

### Quick Rollback (Same Image)
```bash
# If you need to redeploy the same code
make deploy-prod
```

### Rollback to Previous Code
```bash
# 1. Checkout previous commit
git checkout HEAD~1

# 2. Deploy that version
make deploy-prod

# 3. Return to latest code (when fixed)
git checkout main
```

### Emergency Rollback (AWS Console)
1. Go to AWS Lambda console
2. Find function: `prod-gym-app`
3. Click "Versions"
4. Find previous version
5. Update alias to point to it

---

## Common Issues

### "Stack does not exist"
**First deployment:** Takes 15-20 minutes (creates RDS database)
```bash
make deploy-staging
# Wait 15-20 minutes for initial setup
```

### "Image not found"
**ECR repository doesn't exist yet:** Create it manually
```bash
aws ecr create-repository \
  --repository-name gym-app \
  --region us-west-1
```

### "Access Denied"
**AWS credentials not set:** Configure AWS CLI
```bash
aws configure
# Enter: Access Key, Secret Key, Region: us-west-1
```

### Check AWS Setup
```bash
make check-aws
# Shows: Account ID, Region, ECR status
```

---

## Monitoring After Deployment

### Check Application Health
```bash
# Staging
curl https://staging.titantrakr.com/api/health

# Production
curl https://titantrakr.com/api/health
```

### View Lambda Logs (AWS Console)
1. Go to CloudWatch Logs
2. Find log group: `/aws/lambda/prod-gym-app` or `staging-gym-app`
3. View recent log streams

### View Lambda Logs (CLI)
```bash
# Last 10 minutes of production logs
aws logs tail /aws/lambda/prod-gym-app --follow --region us-west-1

# Last 10 minutes of staging logs
aws logs tail /aws/lambda/staging-gym-app --follow --region us-west-1
```

---

## Cost of Deployments

**Each deployment:**
- Docker build: Free (local CPU)
- ECR storage: $0.10/GB/month (~$0.03/month)
- Lambda image pull: Free (within AWS)
- Lambda invocations: Free tier (1M requests/month)

**Total cost to deploy 10 times/day:** Essentially $0

---

## Tips

### Fast Iteration on Staging
```bash
# Make change → Deploy → Test → Repeat
vim backend/api/voice.py
make deploy-staging  # ~2 min
# Test on staging.titantrakr.com
```

### Deploy Only When Ready for Production
```bash
# No rush! Deploy to prod only when:
# - Staging is stable
# - Features are complete
# - You've tested thoroughly
make deploy-prod
```

### Git Push ≠ Deploy
```bash
# This is safe - does NOT deploy
git push origin main

# Deploy happens only when YOU run:
make deploy-staging  # or
make deploy-prod
```

---

## Architecture

```
Developer Local Machine
    ↓ (make deploy-staging)
Docker Build → ECR → Lambda Update
    ↓
AWS Lambda (FastAPI)
    ↓
RDS PostgreSQL
```

**Key point:** You control the trigger, not Git!

---

## Questions?

- **"Can I auto-deploy on git push?"**  
  Yes, but not recommended for solo MVP. Keep manual control.

- **"What if I break production?"**  
  Rollback to previous commit and redeploy (~3 minutes)

- **"How do I know it worked?"**  
  Script shows health check result + URLs

- **"Can I deploy from any branch?"**  
  Yes! Script deploys whatever code is currently checked out locally

---

## Next Steps

1. Test local: `make test-local`
2. Deploy to staging: `make deploy-staging`
3. Test staging: https://staging.titantrakr.com
4. Deploy to prod: `make deploy-prod`
5. Test production: https://titantrakr.com

**Remember:** Pushing to git does nothing. You deploy when YOU decide!

