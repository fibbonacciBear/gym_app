#!/bin/bash
# Quick deploy to production - single command
# Usage: ./deploy-quick.sh [optional-environment]

set -e

# Default to staging for safety
ENVIRONMENT=${1:-staging}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Quick Deploy to $ENVIRONMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Confirm production deployments
if [ "$ENVIRONMENT" = "prod" ]; then
  echo "⚠️  You're about to deploy to PRODUCTION"
  read -p "Are you sure? (yes/no): " confirm
  if [ "$confirm" != "yes" ]; then
    echo "❌ Deployment cancelled"
    exit 0
  fi
fi

# Run full deployment
./infrastructure/scripts/deploy.sh $ENVIRONMENT

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

