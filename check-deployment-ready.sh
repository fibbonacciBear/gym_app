#!/bin/bash
# Check if ready for AWS deployment

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Pre-Deployment Readiness Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

READY=true

# Check 1: AWS CLI
echo "1. Checking AWS CLI..."
if command -v aws &> /dev/null; then
    echo "   ✅ AWS CLI installed"
    
    # Check credentials
    if aws sts get-caller-identity &> /dev/null; then
        ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
        echo "   ✅ AWS credentials configured (Account: $ACCOUNT)"
    else
        echo "   ❌ AWS credentials NOT configured"
        echo "      Run: aws configure"
        READY=false
    fi
else
    echo "   ❌ AWS CLI not installed"
    echo "      Install: https://aws.amazon.com/cli/"
    READY=false
fi
echo ""

# Check 2: ECR Repository
echo "2. Checking ECR repository..."
if aws ecr describe-repositories --repository-names gym-app --region us-west-1 &> /dev/null; then
    echo "   ✅ ECR repository exists"
else
    echo "   ❌ ECR repository NOT created"
    echo "      Run: aws ecr create-repository --repository-name gym-app --region us-west-1"
    READY=false
fi
echo ""

# Check 3: Route53 Hosted Zone
echo "3. Checking Route53 hosted zone..."
ZONE_COUNT=$(aws route53 list-hosted-zones --query "HostedZones[?Name=='titantrakr.com.']" --output text 2>/dev/null | wc -l)
if [ "$ZONE_COUNT" -gt 0 ]; then
    echo "   ✅ Route53 hosted zone exists for titantrakr.com"
else
    echo "   ⚠️  Route53 hosted zone NOT found for titantrakr.com"
    echo "      (Optional: Create with: aws route53 create-hosted-zone --name titantrakr.com)"
    echo "      Or deploy without custom domain first"
fi
echo ""

# Check 4: Secrets Configuration
echo "4. Checking deployment parameters..."
if grep -q "CHANGE_ME" infrastructure/deploy-parameters-staging.json; then
    echo "   ❌ Secrets NOT configured in deploy-parameters-staging.json"
    echo "      Edit file and replace:"
    echo "      - CHANGE_ME_STRONG_PASSWORD_HERE → strong database password"
    echo "      - CHANGE_ME_YOUR_ANTHROPIC_KEY → your Anthropic API key"
    READY=false
else
    echo "   ✅ Secrets configured in deploy-parameters-staging.json"
fi
echo ""

# Check 5: Docker
echo "5. Checking Docker..."
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        echo "   ✅ Docker installed and running"
    else
        echo "   ❌ Docker installed but NOT running"
        echo "      Start Docker Desktop"
        READY=false
    fi
else
    echo "   ❌ Docker not installed"
    echo "      Install: https://docs.docker.com/get-docker/"
    READY=false
fi
echo ""

# Check 6: Python dependencies
echo "6. Checking Python dependencies..."
if [ -f "requirements.txt" ]; then
    echo "   ✅ requirements.txt exists"
    if python3 -c "import fastapi" &> /dev/null; then
        echo "   ✅ Python dependencies installed"
    else
        echo "   ⚠️  Python dependencies NOT installed"
        echo "      Run: pip install -r requirements.txt"
    fi
else
    echo "   ❌ requirements.txt not found"
    READY=false
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ "$READY" = true ]; then
    echo "✅ READY TO DEPLOY!"
    echo ""
    echo "Next steps:"
    echo "1. Test locally: make test-local"
    echo "2. Deploy staging: make deploy-staging"
    echo ""
    echo "Expected deployment time: 20-25 minutes (first time)"
else
    echo "❌ NOT READY - Fix issues above first"
    echo ""
    echo "See: PRE_DEPLOYMENT_CHECKLIST.md for detailed instructions"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

