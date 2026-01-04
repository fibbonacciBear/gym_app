# Gym App - Simple Deployment Commands
# Usage: make deploy-staging   OR   make deploy-prod

.PHONY: help deploy-staging deploy-prod deploy-fast test-local check-aws

help:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "🏋️  Gym App Deployment Commands"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "Local Development:"
	@echo "  make test-local     Run app locally (http://localhost:8000)"
	@echo ""
	@echo "AWS Deployment:"
	@echo "  make deploy-staging Deploy to staging.titantrakr.com"
	@echo "  make deploy-prod    Deploy to titantrakr.com (asks for confirmation)"
	@echo ""
	@echo "Utilities:"
	@echo "  make check-aws      Check AWS credentials and region"
	@echo ""

# Deploy to staging (safe, no confirmation needed)
deploy-staging:
	@echo "🚀 Deploying to STAGING..."
	./deploy-staging.sh

# Deploy to production (asks for confirmation)
deploy-prod:
	@echo "⚠️  Deploying to PRODUCTION"
	@./deploy-production.sh

# Test locally
test-local:
	@echo "🏃 Running local development server..."
	@echo "📍 http://localhost:8000"
	python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Check AWS configuration
check-aws:
	@echo "🔍 Checking AWS configuration..."
	@echo ""
	@echo "AWS Account:"
	@aws sts get-caller-identity --query 'Account' --output text || echo "❌ Not logged in"
	@echo ""
	@echo "Default Region:"
	@aws configure get region || echo "❌ Not configured"
	@echo ""
	@echo "ECR Repository:"
	@aws ecr describe-repositories --repository-names gym-app --region us-west-1 --query 'repositories[0].repositoryUri' --output text 2>/dev/null || echo "⚠️  Not created yet"

