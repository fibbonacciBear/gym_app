# Production Deployment Guide

## Quick Start (20-30 minutes)

Now that staging is working, production deployment is **straightforward**!

---

## Step-by-Step Instructions

### **1. Create SSL Certificate in us-east-1** (2 min)

```bash
# Request certificate for production domain
aws acm request-certificate \
  --domain-name titantrakr.com \
  --domain-name www.titantrakr.com \
  --validation-method DNS \
  --region us-east-1
```

**Copy the Certificate ARN** from the output!

The DNS validation should complete **instantly** since Route53 will auto-create the validation record.

---

### **2. Generate Production Database Password** (1 min)

```bash
# Generate a secure password (different from staging!)
openssl rand -base64 32 | tr -d '/+='
```

---

### **3. Update Production Parameters** (2 min)

Edit: `infrastructure/deploy-parameters-simple-production.json`

Replace:
- `CHANGE_ME_DIFFERENT_PASSWORD_FROM_STAGING` → your new DB password
- `PASTE_PRODUCTION_CERTIFICATE_ARN_HERE` → certificate ARN from step 1

---

### **4. Deploy to Production** (15-20 min)

```bash
./deploy-production.sh
```

**Important:** The script will ask for confirmation before deploying to production.

**What happens:**
1. Builds and pushes Docker image tagged as `production`
2. Creates CloudFormation stack: `gym-app-production`
3. Creates:
   - Lambda function
   - RDS PostgreSQL database
   - VPC + NAT Gateway
   - CloudFront distribution
   - Route53 DNS record for `titantrakr.com`

---

### **5. Initialize Production Database** (1 min)

After deployment completes:

```bash
curl -X POST https://titantrakr.com/api/admin/init-db
```

This creates tables and loads 20 default exercises.

---

### **6. Update Auth0 for Production** (2 min)

Go to Auth0 Dashboard → TitanTrakr SPA → Settings

**Add production URLs to:**
- **Allowed Callback URLs**: Add `https://titantrakr.com`
- **Allowed Logout URLs**: Add `https://titantrakr.com`
- **Allowed Web Origins**: Add `https://titantrakr.com`
- **Allowed Origins (CORS)**: Add `https://titantrakr.com`

(Keep staging and localhost URLs!)

Click **Save Changes**

---

### **7. Test Production** (5 min)

1. Open https://titantrakr.com
2. Click "Log In"
3. Create a test account
4. Try voice recording
5. Check workout history

---

## Production vs Staging Differences

| Aspect | Staging | Production |
|--------|---------|------------|
| **Domain** | `staging.titantrakr.com` | `titantrakr.com` |
| **Stack Name** | `gym-app-staging-simple` | `gym-app-production` |
| **Docker Tag** | `staging` | `production` |
| **Lambda Name** | `staging-gym-app` | `production-gym-app` |
| **DB Password** | Different | Different (more secure) |
| **RDS Name** | `staging-gym-app-db` | `production-gym-app-db` |
| **CloudFront** | Different distribution | Different distribution |

---

## Post-Deployment Checklist

✅ **Immediately:**
- [ ] Initialize database (`/api/admin/init-db`)
- [ ] Update Auth0 callback URLs
- [ ] Test user registration
- [ ] Test voice recording
- [ ] Verify workout history

✅ **Within 24 hours:**
- [ ] Monitor CloudWatch logs for errors
- [ ] Check Lambda cold start times
- [ ] Verify RDS database metrics
- [ ] Test under moderate load

✅ **Within 1 week:**
- [ ] Set up CloudWatch alarms (errors, latency)
- [ ] Review costs in AWS Cost Explorer
- [ ] Consider RDS Proxy if high traffic
- [ ] Set up AWS Backup if needed

---

## Rollback Plan

If production has issues:

1. **Keep staging running** (it's independent)
2. **Roll back DNS** to staging:
   ```bash
   # Point production domain to staging (emergency)
   # Manual Route53 change: titantrakr.com → staging CloudFront
   ```
3. **Delete production stack**:
   ```bash
   aws cloudformation delete-stack \
     --stack-name gym-app-production \
     --region us-west-1
   ```

---

## Cost Estimate

**Production monthly costs** (similar to staging):
- Lambda: $5-10
- RDS PostgreSQL: $15-25 (db.t3.micro)
- NAT Gateway: $32
- CloudFront: $1-5
- Route53: $0.50

**Total: ~$55-75/month**

---

## Support

If you run into issues:
1. Check CloudWatch logs: `/aws/lambda/production-gym-app`
2. Review staging deployment (it works!)
3. Compare CloudFormation stack events
4. Verify certificate is in us-east-1

---

**Ready to deploy to production?** 🚀

Just run: `./deploy-production.sh`


