# Pre-Deployment Checklist

## Status: ⚠️ NOT READY - Complete these steps first

Before running `make deploy-staging`, you need to complete the following setup:

---

## ✅ 1. AWS Account Setup

### Check AWS CLI Configuration
```bash
make check-aws
```

**Expected output:**
```
AWS Account: 273354662815
Default Region: us-west-1
ECR Repository: 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app
```

**If not configured:**
```bash
aws configure
# Enter your:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Region: us-west-1
# - Output format: json
```

---

## ⚠️ 2. Create ECR Repository (One-time)

Before first deployment, create the Docker image repository:

```bash
aws ecr create-repository \
  --repository-name gym-app \
  --region us-west-1 \
  --image-scanning-configuration scanOnPush=true
```

**Verify it exists:**
```bash
aws ecr describe-repositories \
  --repository-names gym-app \
  --region us-west-1
```

---

## ⚠️ 3. Domain Setup (titantrakr.com)

### Check if Route53 Hosted Zone Exists
```bash
aws route53 list-hosted-zones \
  --query "HostedZones[?Name=='titantrakr.com.']" \
  --region us-west-1
```

### If NOT exists, create it:
```bash
aws route53 create-hosted-zone \
  --name titantrakr.com \
  --caller-reference $(date +%s) \
  --hosted-zone-config Comment="Gym App DNS"
```

**Important:** Update your domain registrar's nameservers to point to Route53:
1. Get nameservers: `aws route53 get-hosted-zone --id YOUR_ZONE_ID`
2. Copy the 4 NS records (e.g., `ns-123.awsdns-12.com`)
3. Update at your domain registrar (GoDaddy, Namecheap, etc.)
4. **Wait 24-48 hours** for DNS propagation

---

## ⚠️ 4. Configure Secrets (REQUIRED)

### Update Staging Parameters
Edit: `infrastructure/deploy-parameters-staging.json`

```bash
vim infrastructure/deploy-parameters-staging.json
```

**Required changes:**
```json
{
  "ParameterKey": "DBMasterPassword",
  "ParameterValue": "CHANGE_ME_STRONG_PASSWORD_HERE"  ← Generate strong password
},
{
  "ParameterKey": "AnthropicApiKey",
  "ParameterValue": "CHANGE_ME_YOUR_ANTHROPIC_KEY"  ← Add your Anthropic API key
}
```

**How to generate a strong password:**
```bash
# Option 1: Random password
openssl rand -base64 32

# Option 2: Readable password
openssl rand -base64 16 | tr -dc 'A-Za-z0-9' | head -c 20
```

**How to get Anthropic API key:**
1. Go to: https://console.anthropic.com/
2. Navigate to: Settings → API Keys
3. Create new key
4. Copy and paste into deploy-parameters-staging.json

### Update Production Parameters
Edit: `infrastructure/deploy-parameters.json`

```bash
vim infrastructure/deploy-parameters.json
```

**Use DIFFERENT passwords for production!**

---

## ⚠️ 5. Test Locally First

Before deploying to AWS, verify the app works locally:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export ANTHROPIC_API_KEY="your-key-here"
export USE_OPENAI="false"

# 3. Run locally
make test-local
```

**Visit:** http://localhost:8000

**Test these features:**
- ✅ Home page loads
- ✅ Health endpoint: http://localhost:8000/api/health
- ✅ Start a workout
- ✅ Log a set (with voice or manual)
- ✅ Complete workout

---

## ⚠️ 6. Review Costs

### First Deployment (One-time costs)
- CloudFormation stack creation: **15-20 minutes**
- RDS database initialization: **~10 minutes** (part of above)
- ACM certificate validation: **5-30 minutes** (DNS validation)

### Monthly Costs (Staging)
- RDS PostgreSQL (t4g.micro): **~$12/month** (or $5 if stopped nightly)
- CloudFront: **~$1/month**
- Lambda: **$0** (free tier)
- Route53: **$0.50/month**
- Anthropic API: **~$5-10/month** (usage-based)
- **Total: ~$18-28/month**

### Monthly Costs (Production)
- Same as staging: **~$31/month**
- Plus RDS Proxy: **+$11/month**
- Plus AWS Backup: **+$2/month**
- **Total: ~$44/month**

**Both environments: ~$50-60/month**

---

## 📋 Pre-Deployment Command Checklist

Run these to verify everything is ready:

```bash
# 1. Check AWS credentials
make check-aws

# 2. Check ECR repository exists
aws ecr describe-repositories --repository-names gym-app --region us-west-1

# 3. Check Route53 hosted zone exists
aws route53 list-hosted-zones | grep titantrakr.com

# 4. Verify secrets are set (not the placeholder text)
grep -v "CHANGE_ME" infrastructure/deploy-parameters-staging.json | grep "ParameterValue"

# 5. Test local app works
make test-local
# (Ctrl+C to stop after testing)
```

**All checks passed?** → Ready to deploy! ✅

---

## 🚀 First Deployment (Staging)

Once all checks pass:

```bash
make deploy-staging
```

**What happens:**
1. ✅ Builds Docker image (~2 min)
2. ✅ Pushes to ECR (~1 min)
3. ✅ Creates CloudFormation stack (~15-20 min)
   - VPC, subnets, security groups
   - RDS PostgreSQL database
   - Lambda function
   - CloudFront distribution
   - ACM SSL certificate
   - Route53 DNS records
4. ✅ Tests health endpoint

**Total time: ~20-25 minutes**

**Expected output:**
```
🚀 Deploying to staging...
📦 Building and pushing Docker image...
🆕 Creating new CloudFormation stack...
⏳ Waiting for stack creation (15-20 minutes)...
✅ Stack created successfully!

📊 Deployment Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🌐 Primary URL:    https://staging.titantrakr.com
⚡ Lambda URL:     https://xyz123.lambda-url.us-west-1.on.aws
🗄️  Database:       staging-gym-app-db.abc123.us-west-1.rds.amazonaws.com

✅ Deployment complete!
```

---

## 🔍 Post-Deployment Verification

### 1. Check Health Endpoint
```bash
curl https://staging.titantrakr.com/api/health
```

**Expected:**
```json
{"status": "healthy", "database": "connected"}
```

### 2. Check CloudFormation Stack
```bash
aws cloudformation describe-stacks \
  --stack-name gym-app-staging \
  --region us-west-1 \
  --query 'Stacks[0].StackStatus'
```

**Expected:** `"CREATE_COMPLETE"` or `"UPDATE_COMPLETE"`

### 3. Check Lambda Function
```bash
aws lambda get-function \
  --function-name staging-gym-app \
  --region us-west-1 \
  --query 'Configuration.State'
```

**Expected:** `"Active"`

### 4. Check RDS Database
```bash
aws rds describe-db-instances \
  --db-instance-identifier staging-gym-app-db \
  --region us-west-1 \
  --query 'DBInstances[0].DBInstanceStatus'
```

**Expected:** `"available"`

### 5. Browse the App
Open: https://staging.titantrakr.com

**Test full user flow:**
- ✅ Page loads
- ✅ Start workout
- ✅ Add exercise
- ✅ Log a set
- ✅ Complete workout
- ✅ View history

---

## 🐛 Common First-Deployment Issues

### Issue 1: "Certificate validation pending"
**Cause:** ACM certificate waiting for DNS validation

**Fix:**
```bash
# Check certificate status
aws acm list-certificates --region us-east-1

# If stuck, check if Route53 validation records were created
aws route53 list-resource-record-sets \
  --hosted-zone-id YOUR_ZONE_ID | grep _acm
```

**Solution:** Wait 5-30 minutes for DNS propagation

---

### Issue 2: "DBMasterPassword too short"
**Cause:** Password < 8 characters

**Fix:**
```bash
# Generate strong password
openssl rand -base64 32

# Update deploy-parameters-staging.json
# Redeploy
```

---

### Issue 3: "ECR repository does not exist"
**Cause:** Forgot to create ECR repository

**Fix:**
```bash
aws ecr create-repository \
  --repository-name gym-app \
  --region us-west-1
```

---

### Issue 4: "Access Denied" errors
**Cause:** AWS IAM permissions missing

**Fix:**
- Check your AWS user has these policies:
  - `AWSCloudFormationFullAccess`
  - `AmazonEC2ContainerRegistryFullAccess`
  - `AWSLambda_FullAccess`
  - `AmazonRDSFullAccess`
  - `AmazonVPCFullAccess`
  - `IAMFullAccess` (to create roles)

---

### Issue 5: "Hosted zone not found"
**Cause:** Route53 zone doesn't exist

**Fix:**
```bash
# Create hosted zone
aws route53 create-hosted-zone \
  --name titantrakr.com \
  --caller-reference $(date +%s)

# Get nameservers
aws route53 get-hosted-zone --id YOUR_ZONE_ID

# Update at your domain registrar
# Wait 24 hours for propagation
```

---

## 📝 Deployment Order

**Recommended approach:**

1. ✅ **Staging first** (safe to break)
   ```bash
   make deploy-staging
   ```

2. ✅ **Test staging thoroughly** (1-2 days)
   - Create workouts
   - Test voice commands
   - Test templates
   - Check database persistence

3. ✅ **Deploy production** (when confident)
   ```bash
   make deploy-prod
   ```

---

## ✅ Final Checklist

Before running `make deploy-staging`, confirm:

- [ ] AWS CLI configured (`make check-aws`)
- [ ] ECR repository created
- [ ] Route53 hosted zone created for titantrakr.com
- [ ] Domain nameservers updated (if new domain)
- [ ] `deploy-parameters-staging.json` updated with:
  - [ ] Strong database password (not "CHANGE_ME")
  - [ ] Anthropic API key (not "CHANGE_ME")
- [ ] App tested locally (`make test-local`)
- [ ] Budget approved (~$20/month staging, ~$44/month production)

**All checked?** → You're ready! 🚀

```bash
make deploy-staging
```

---

## 🆘 Need Help?

If you encounter issues during deployment:

1. **Check CloudFormation events:**
   ```bash
   aws cloudformation describe-stack-events \
     --stack-name gym-app-staging \
     --region us-west-1 \
     --max-items 20
   ```

2. **Check Lambda logs:**
   ```bash
   aws logs tail /aws/lambda/staging-gym-app \
     --follow \
     --region us-west-1
   ```

3. **Rollback if needed:**
   ```bash
   aws cloudformation delete-stack \
     --stack-name gym-app-staging \
     --region us-west-1
   ```

4. **Common error messages:**
   - "CREATE_FAILED" → Check CloudFormation events for specific resource
   - "ROLLBACK_COMPLETE" → Stack failed, check events, delete, retry
   - "Certificate validation timeout" → Check Route53 DNS records

---

## Next Steps After Successful Deployment

1. ✅ Initialize database schema (if needed)
2. ✅ Test all features on staging
3. ✅ Set up monitoring (CloudWatch dashboards)
4. ✅ Configure backups (already automated)
5. ✅ Deploy to production (when ready)

**Good luck with your deployment!** 🎉

