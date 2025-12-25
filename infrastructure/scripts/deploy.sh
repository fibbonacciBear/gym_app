#!/bin/bash
# Deploy gym app to AWS using CloudFormation
set -e

ENVIRONMENT=$1

if [ "$ENVIRONMENT" != "prod" ] && [ "$ENVIRONMENT" != "staging" ]; then
  echo "Usage: ./deploy.sh [prod|staging]"
  exit 1
fi

REGION="us-west-1"
STACK_NAME="gym-app-$ENVIRONMENT"
TEMPLATE_FILE="infrastructure/cloudformation-template.yaml"
PARAMS_FILE="infrastructure/deploy-parameters-$ENVIRONMENT.json"

echo "🚀 Deploying $ENVIRONMENT environment..."

# 1. Build and push Docker image
echo "📦 Building and pushing Docker image..."
./infrastructure/scripts/build-and-push.sh $ENVIRONMENT

# 2. Check if stack exists
echo "🔍 Checking if stack exists..."
STACK_EXISTS=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION 2>/dev/null && echo "true" || echo "false")

if [ "$STACK_EXISTS" = "false" ]; then
  # Create new stack
  echo "🆕 Creating new CloudFormation stack..."
  echo "⚠️  This will take 15-20 minutes (RDS creation is slow)"
  
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
  # Update Lambda function code only (fast path)
  echo "🔄 Stack exists, updating Lambda function code..."
  
  FUNCTION_NAME="${ENVIRONMENT}-gym-app"
  IMAGE_URI="273354662815.dkr.ecr.${REGION}.amazonaws.com/gym-app:${ENVIRONMENT}"
  
  aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --image-uri $IMAGE_URI \
    --region $REGION
  
  echo "⏳ Waiting for function update..."
  aws lambda wait function-updated \
    --function-name $FUNCTION_NAME \
    --region $REGION
  
  echo "✅ Lambda function updated!"
fi

# 3. Get outputs
echo ""
echo "📊 Deployment Details:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PRIMARY_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`PrimaryDomainURL`].OutputValue' \
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

echo "🌐 Primary URL:    $PRIMARY_URL"
echo "⚡ Lambda URL:     $LAMBDA_URL"
echo "🗄️  Database:       $DB_ENDPOINT"
echo ""

# 4. Test health endpoint
echo "🏥 Testing health endpoint..."
if [ "$PRIMARY_URL" != "N/A" ]; then
  HEALTH_RESPONSE=$(curl -s $PRIMARY_URL/api/health || echo "Connection failed")
  echo "Response: $HEALTH_RESPONSE"
else
  echo "⚠️  Primary URL not available yet (DNS/SSL may still be propagating)"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
if [ "$STACK_EXISTS" = "false" ]; then
  echo "1. Check ACM certificate validation (DNS records may need approval)"
  echo "2. Wait for DNS propagation (can take 5-30 minutes)"
  echo "3. Initialize database schema (run migrations)"
fi
echo "4. Test the application at $PRIMARY_URL"



