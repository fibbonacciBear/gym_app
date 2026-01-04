#!/bin/bash
# Quick deploy - wrapper for staging/production deployment scripts
# Usage: ./deploy-quick.sh [staging|prod]

set -e

# Default to staging for safety
ENVIRONMENT=${1:-staging}

# Route to appropriate deployment script
if [ "$ENVIRONMENT" = "prod" ]; then
  ./deploy-production.sh
elif [ "$ENVIRONMENT" = "staging" ]; then
  ./deploy-staging.sh
else
  echo "❌ Invalid environment: $ENVIRONMENT"
  echo "Usage: ./deploy-quick.sh [staging|prod]"
  exit 1
fi

