#!/bin/bash
# Simple deployment script - uses minimal template
set -e

ENVIRONMENT="staging"
REGION="us-west-1"
STACK_NAME="gym-app-${ENVIRONMENT}-simple"
TEMPLATE_FILE="infrastructure/cloudformation-simple.yaml"
PARAMS_FILE="infrastructure/deploy-parameters-simple-staging.json"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Simple Deployment to ${ENVIRONMENT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

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
  echo "⏳ This will take ~8-10 minutes (RDS creation)"
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
  # Update entire stack (includes CloudFront, certificates, etc.)
  echo "🔄 Stack exists, updating stack with new resources..."
  echo "⏳ This may take 15-20 minutes (CloudFront distribution + SSL certificate)"
  
  aws cloudformation update-stack \
    --stack-name $STACK_NAME \
    --template-body file://$TEMPLATE_FILE \
    --parameters file://$PARAMS_FILE \
    --capabilities CAPABILITY_IAM \
    --region $REGION || echo "No updates needed"
  
  echo "⏳ Waiting for stack update..."
  aws cloudformation wait stack-update-complete \
    --stack-name $STACK_NAME \
    --region $REGION 2>/dev/null || echo "Stack already up to date"
  
  echo "✅ Stack updated successfully!"
fi

# 3. Get outputs
echo ""
echo "📊 Deployment Details:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

LAMBDA_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionURL`].OutputValue' \
  --output text 2>/dev/null || echo "N/A")

CUSTOM_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`CustomDomainURL`].OutputValue' \
  --output text 2>/dev/null || echo "")

DB_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
  --output text 2>/dev/null || echo "N/A")

if [ -n "$CUSTOM_URL" ]; then
  echo "🌐 Custom Domain: $CUSTOM_URL"
fi
echo "🌐 Lambda URL:    $LAMBDA_URL"
echo "🗄️  Database:       $DB_ENDPOINT"
echo ""

# 4. Invalidate CloudFront cache (force fresh content)
if [ -n "$CUSTOM_URL" ]; then
  echo "🔄 Invalidating CloudFront cache..."
  CF_DIST_ID=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
    --output text 2>/dev/null)
  
  if [ -n "$CF_DIST_ID" ] && [ "$CF_DIST_ID" != "None" ]; then
    aws cloudfront create-invalidation \
      --distribution-id $CF_DIST_ID \
      --paths "/*" \
      --query 'Invalidation.Id' \
      --output text
    echo "✅ CloudFront cache invalidated (all paths)"
  fi
fi
echo ""

# 5. Test health endpoint
echo "🏥 Testing health endpoint..."
if [ "$LAMBDA_URL" != "N/A" ]; then
  sleep 5  # Give Lambda a moment to be ready
  HEALTH_RESPONSE=$(curl -s ${LAMBDA_URL}api/health || echo "Connection failed")
  echo "Response: $HEALTH_RESPONSE"
else
  echo "⚠️  Lambda URL not available yet"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🎉 Your app is live at:"
if [ -n "$CUSTOM_URL" ]; then
  echo "   $CUSTOM_URL"
else
  echo "   $LAMBDA_URL"
fi
echo ""
echo "Next steps:"
echo "1. Open the URL in your browser"
echo "2. Test the application"
echo "3. Check CloudWatch logs if needed"

