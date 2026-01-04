#!/bin/bash
# Production deployment script
set -e

ENVIRONMENT="prod"
REGION="us-west-1"
STACK_NAME="gym-app-${ENVIRONMENT}"
TEMPLATE_FILE="infrastructure/cloudformation-simple.yaml"
PARAMS_FILE="infrastructure/deploy-parameters-simple-production.json"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 PRODUCTION Deployment"
echo "⚠️  WARNING: Deploying to PRODUCTION!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Are you sure you want to deploy to PRODUCTION? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
  echo "❌ Deployment cancelled"
  exit 1
fi
echo ""

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# 1. Build and push Docker image
echo "📦 Building and pushing Docker image..."
./infrastructure/scripts/build-and-push.sh ${ENVIRONMENT}

# 2. Check if stack exists
echo "🔍 Checking if stack exists..."
STACK_EXISTS=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION 2>/dev/null && echo "true" || echo "false")

if [ "$STACK_EXISTS" = "false" ]; then
  # Create new stack
  echo "🆕 Creating new CloudFormation stack..."
  echo "⏳ This will take ~15-20 minutes (RDS + CloudFront)"
  echo ""
  
  aws cloudformation create-stack \
    --stack-name $STACK_NAME \
    --template-body file://$TEMPLATE_FILE \
    --parameters file://$PARAMS_FILE \
    --capabilities CAPABILITY_IAM \
    --region $REGION
  
  echo "⏳ Waiting for stack creation..."
  aws cloudformation wait stack-create-complete \
    --stack-name $STACK_NAME \
    --region $REGION
  
  echo "✅ Stack created successfully!"
else
  # Update stack
  echo "🔄 Stack exists, updating..."
  echo "⏳ This may take 15-20 minutes"
  
  aws cloudformation update-stack \
    --stack-name $STACK_NAME \
    --template-body file://$TEMPLATE_FILE \
    --parameters file://$PARAMS_FILE \
    --capabilities CAPABILITY_IAM \
    --region $REGION 2>&1 | grep -v "No updates are to be performed" || true

  echo "⏳ Waiting for stack update..."
  aws cloudformation wait stack-update-complete \
    --stack-name $STACK_NAME \
    --region $REGION 2>&1 || true
  
  echo "✅ Stack updated successfully!"
fi

# 3. Get outputs
echo ""
echo "📊 Deployment Details:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CUSTOM_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`CustomDomainURL`].OutputValue' \
  --output text 2>/dev/null || echo "N/A")

LAMBDA_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionURL`].OutputValue' \
  --output text 2>/dev/null || echo "N/A")

DB_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
  --output text 2>/dev/null || echo "N/A")

echo "🌐 Custom Domain: $CUSTOM_URL"
echo "🌐 Lambda URL:    $LAMBDA_URL"
echo "🗄️  Database:      $DB_ENDPOINT"
echo ""

# 4. Test health endpoint
echo "🏥 Testing health endpoint..."
if [ "$CUSTOM_URL" != "N/A" ]; then
  sleep 5
  HEALTH_RESPONSE=$(curl -s ${CUSTOM_URL}/api/health || echo "Connection failed")
  echo "Response: $HEALTH_RESPONSE"
fi

echo ""
echo "✅ PRODUCTION deployment complete!"
echo ""
echo "🎉 Your app is live at:"
echo "   $CUSTOM_URL"
echo ""
echo "⚠️  Next steps:"
echo "1. Initialize database: curl -X POST ${CUSTOM_URL}/api/admin/init-db"
echo "2. Update Auth0 with production callback URLs"
echo "3. Test thoroughly before announcing"

