# Gym App AWS Deployment Guide

## Architecture Overview

```
User → Route53 → CloudFront → Lambda Function URL → Lambda (FastAPI + Mangum)
                                                        ↓
                                                    RDS Proxy
                                                        ↓
                                                    RDS PostgreSQL
```

**Replicates your PassportPhotoFactory pattern** with PostgreSQL instead of DynamoDB.

---

## Prerequisites

1. AWS CLI configured (`aws configure`)
2. Docker installed (for building Lambda image)
3. ECR repository created
4. Domains registered and Route53 hosted zones created ✅ (already done)

---

## Deployment Steps

### Step 1: Build and Push Docker Image

```bash
# Navigate to project root
cd /Users/akashganesan/Documents/code/gym_app

# Create ECR repository
aws ecr create-repository \
  --repository-name gym-app \
  --region us-west-1

# Get ECR login
aws ecr get-login-password --region us-west-1 | \
  docker login --username AWS --password-stdin \
  273354662815.dkr.ecr.us-west-1.amazonaws.com

# Build Docker image
docker build -t gym-app:prod -f infrastructure/Dockerfile .

# Tag for ECR
docker tag gym-app:prod \
  273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod

# Push to ECR
docker push 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod
```

### Step 2: Update Parameters

Edit `infrastructure/deploy-parameters.json` and set:
- `DBMasterPassword` - Strong password (min 8 chars)
- `AnthropicApiKey` - Your Anthropic API key
- `OpenAIApiKey` - (optional) Your OpenAI key

### Step 3: Deploy CloudFormation Stack

```bash
aws cloudformation create-stack \
  --stack-name gym-app-prod \
  --template-body file://infrastructure/cloudformation-template.yaml \
  --parameters file://infrastructure/deploy-parameters.json \
  --capabilities CAPABILITY_IAM \
  --region us-west-1

# Monitor deployment
aws cloudformation describe-stacks \
  --stack-name gym-app-prod \
  --region us-west-1 \
  --query 'Stacks[0].StackStatus'

# Or watch in real-time
aws cloudformation wait stack-create-complete \
  --stack-name gym-app-prod \
  --region us-west-1
```

**Expected time:** 15-20 minutes (RDS takes ~10 min)

### Step 4: Validate SSL Certificates (DNS Validation)

After stack creates, you need to validate SSL certificates:

```bash
# Get certificate validation records
aws acm describe-certificate \
  --certificate-arn $(aws cloudformation describe-stacks \
    --stack-name gym-app-prod \
    --region us-west-1 \
    --query 'Stacks[0].Outputs[?OutputKey==`SSLCertificateArn`].OutputValue' \
    --output text) \
  --region us-east-1 \
  --query 'Certificate.DomainValidationOptions[].[DomainName,ResourceRecord.Name,ResourceRecord.Value]' \
  --output table
```

**Add the CNAME records** to Route53 for each domain (AWS may auto-add them if you used Route53 for DNS).

### Step 5: Initialize Database Schema

```bash
# Get database endpoint
DB_HOST=$(aws cloudformation describe-stacks \
  --stack-name gym-app-prod \
  --region us-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
  --output text)

# Connect via psql and run schema creation
# (You'll need to create a migration script or connect manually)
```

### Step 6: Test Deployment

```bash
# Get CloudFront URL
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
  --stack-name gym-app-prod \
  --region us-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontURL`].OutputValue' \
  --output text)

# Test health endpoint
curl https://$CLOUDFRONT_URL/api/health

# Expected: {"status":"healthy","version":"0.1.0"}
```

### Step 7: DNS Propagation

Once SSL certs are validated (Step 4), your domain will be live:
- https://titantrakr.com
- https://www.titantrakr.com

---

## Stack Update (After Code Changes)

```bash
# 1. Build and push new Docker image
docker build -t gym-app:prod -f infrastructure/Dockerfile .
docker tag gym-app:prod 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod
docker push 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod

# 2. Update Lambda function with new image
aws lambda update-function-code \
  --function-name prod-gym-app \
  --image-uri 273354662815.dkr.ecr.us-west-1.amazonaws.com/gym-app:prod \
  --region us-west-1

# 3. Wait for update
aws lambda wait function-updated \
  --function-name prod-gym-app \
  --region us-west-1

echo "Deployment complete!"
```

---

## Cost Estimate

| Component | Cost |
|-----------|------|
| RDS PostgreSQL (db.t4g.micro) | $12/month |
| RDS Proxy | $11/month |
| Lambda (within free tier) | $0 |
| CloudFront (< 1TB) | ~$1-5/month |
| Route53 (3 hosted zones) | $1.50/month |
| **Total** | **~$25-30/month** |

---

## Monitoring

```bash
# Lambda logs
aws logs tail /aws/lambda/prod-gym-app --follow --region us-west-1

# Database connections
aws rds describe-db-proxies \
  --db-proxy-name prod-gym-app-proxy \
  --region us-west-1 \
  --query 'DBProxies[0].Status'

# CloudFront metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront \
  --metric-name Requests \
  --dimensions Name=DistributionId,Value=<DISTRIBUTION_ID> \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum \
  --region us-east-1
```

---

## Cleanup (Delete Stack)

```bash
# WARNING: This deletes everything including database!
aws cloudformation delete-stack \
  --stack-name gym-app-prod \
  --region us-west-1

# Remove ECR images
aws ecr batch-delete-image \
  --repository-name gym-app \
  --image-ids imageTag=prod \
  --region us-west-1
```

---

## Troubleshooting

### Certificate Validation Stuck
- Check Route53 records were created for validation
- Can take 20-30 minutes for DNS propagation
- Check ACM console for validation status

### Lambda Can't Connect to Database
- Verify Lambda is in VPC with internet access (NAT Gateway)
- Check security groups allow Lambda → RDS Proxy → RDS
- Verify RDS Proxy target group points to correct DB

### CloudFront 502 Errors
- Check Lambda function URL is accessible
- Verify Lambda has proper permissions for Function URL
- Check Lambda logs for errors

### Database Connection Errors
- Verify DB credentials in Secrets Manager
- Check RDS Proxy configuration
- Ensure database initialized with tables

---

## Next Steps After Deployment

1. Set up CloudWatch alarms (Lambda errors, RDS CPU)
2. Configure automated backups (RDS does daily by default)
3. Set up monitoring dashboard
4. Configure Route53 health checks
5. Set up CI/CD pipeline (GitHub Actions → ECR → Lambda update)



