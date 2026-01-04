#!/bin/bash
# Build and push Docker image to ECR
set -e

ENVIRONMENT=${1:-staging}
REGION="us-west-1"
ACCOUNT_ID="273354662815"
REPO_NAME="gym-app"
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME"

echo "🔨 Building Docker image for $ENVIRONMENT..."

# Navigate to project root
cd "$(dirname "$0")/../.."

# Build image
docker build \
  --platform linux/amd64 \
  -t $REPO_NAME:$ENVIRONMENT \
  -f infrastructure/Dockerfile \
  .

echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $ECR_URI

echo "🏷️  Tagging image..."
docker tag $REPO_NAME:$ENVIRONMENT $ECR_URI:$ENVIRONMENT

echo "☁️  Pushing to ECR..."
docker push $ECR_URI:$ENVIRONMENT

echo "✅ Image pushed: $ECR_URI:$ENVIRONMENT"





