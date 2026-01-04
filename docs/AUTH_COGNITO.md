# AWS Cognito Authentication Implementation

## Overview
Full-featured authentication using AWS Cognito User Pools with JWT tokens.

## Architecture

```
┌─────────┐         ┌──────────────┐         ┌────────┐         ┌─────┐
│ Browser │ ───────▶│  CloudFront  │ ───────▶│ Lambda │ ───────▶│ RDS │
└─────────┘         └──────────────┘         └────────┘         └─────┘
     │                                             │
     │                                             │
     ▼                                             ▼
┌─────────────┐                            ┌──────────────┐
│   Cognito   │                            │ Verify JWT   │
│  User Pool  │                            │   Token      │
└─────────────┘                            └──────────────┘
```

## Setup Steps

### 1. Create Cognito User Pool (CloudFormation)

Add to `infrastructure/cloudformation-simple.yaml`:

```yaml
  # Cognito User Pool
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub 'gym-app-${EnvironmentName}'
      UsernameAttributes:
        - email
      AutoVerifiedAttributes:
        - email
      EmailConfiguration:
        EmailSendingAccount: COGNITO_DEFAULT
      Schema:
        - Name: email
          AttributeDataType: String
          Required: true
          Mutable: false
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireLowercase: true
          RequireNumbers: true
          RequireSymbols: true
          RequireUppercase: true
      AccountRecoverySetting:
        RecoveryMechanisms:
          - Name: verified_email
            Priority: 1
      UserAttributeUpdateSettings:
        AttributesRequireVerificationBeforeUpdate:
          - email
      MfaConfiguration: OPTIONAL
      EnabledMfas:
        - SOFTWARE_TOKEN_MFA

  # Cognito User Pool Client
  UserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      ClientName: !Sub 'gym-app-client-${EnvironmentName}'
      UserPoolId: !Ref UserPool
      GenerateSecret: false
      ExplicitAuthFlows:
        - ALLOW_USER_SRP_AUTH
        - ALLOW_REFRESH_TOKEN_AUTH
      PreventUserExistenceErrors: ENABLED
      AccessTokenValidity: 1  # 1 hour
      IdTokenValidity: 1      # 1 hour
      RefreshTokenValidity: 30 # 30 days
      TokenValidityUnits:
        AccessToken: hours
        IdToken: hours
        RefreshToken: days

  # Cognito Domain for Hosted UI
  UserPoolDomain:
    Type: AWS::Cognito::UserPoolDomain
    Properties:
      Domain: !Sub 'gym-app-${EnvironmentName}-${AWS::AccountId}'
      UserPoolId: !Ref UserPool

Outputs:
  UserPoolId:
    Description: Cognito User Pool ID
    Value: !Ref UserPool
    Export:
      Name: !Sub '${AWS::StackName}-UserPoolId'

  UserPoolClientId:
    Description: Cognito User Pool Client ID
    Value: !Ref UserPoolClient
    Export:
      Name: !Sub '${AWS::StackName}-UserPoolClientId'

  CognitoHostedUIUrl:
    Description: Cognito Hosted UI URL
    Value: !Sub 'https://gym-app-${EnvironmentName}-${AWS::AccountId}.auth.${AWS::Region}.amazoncognito.com'
```

### 2. Install AWS Cognito JWT Verifier

Update `requirements.txt` and `infrastructure/requirements-lambda.txt`:

```
python-jose[cryptography]==3.3.0
```

### 3. Create Authentication Middleware

```python
# backend/auth.py
from fastapi import Security, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import requests
import os
from functools import lru_cache

security = HTTPBearer()

# Environment variables (set in Lambda)
COGNITO_REGION = os.getenv("COGNITO_REGION", "us-west-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")

@lru_cache()
def get_cognito_public_keys():
    """Fetch and cache Cognito public keys for JWT verification."""
    keys_url = f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json'
    response = requests.get(keys_url)
    return response.json()['keys']

async def verify_cognito_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    Verify Cognito JWT token and return user claims.
    """
    token = credentials.credentials
    
    try:
        # Get the key id from the token header
        headers = jwt.get_unverified_headers(token)
        kid = headers['kid']
        
        # Find the matching public key
        keys = get_cognito_public_keys()
        key = next((k for k in keys if k['kid'] == kid), None)
        
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token key"
            )
        
        # Verify the token
        payload = jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            audience=COGNITO_CLIENT_ID,
            issuer=f'https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}'
        )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

async def get_current_user(token_payload: dict = Depends(verify_cognito_token)) -> str:
    """Extract user_id from Cognito token."""
    # Cognito 'sub' claim is the unique user identifier
    user_id = token_payload.get('sub')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return user_id

async def get_current_user_email(token_payload: dict = Depends(verify_cognito_token)) -> str:
    """Extract email from Cognito token."""
    return token_payload.get('email', '')
```

### 4. Protect API Endpoints

```python
# backend/main.py
from backend.auth import get_current_user, get_current_user_email

@app.post("/api/events")
async def emit_event_endpoint(
    request: EmitEventRequest,
    user_id: str = Depends(get_current_user)
):
    event_record, derived = emit_event(
        event_type=request.event_type,
        payload=request.payload,
        user_id=user_id  # From Cognito JWT
    )
    return EmitEventResponse(...)

@app.get("/api/user/profile")
async def get_user_profile(
    user_id: str = Depends(get_current_user),
    email: str = Depends(get_current_user_email)
):
    return {
        "user_id": user_id,
        "email": email
    }
```

### 5. Frontend Integration (Option A: Hosted UI)

```javascript
// frontend/js/auth.js
const CognitoAuth = {
    region: 'us-west-1',
    userPoolId: 'us-west-1_XXXXXXX',  // From CloudFormation output
    clientId: 'XXXXXXXXXXXXXXXXXXXXXXXXXX',  // From CloudFormation output
    domain: 'gym-app-prod-123456789012.auth.us-west-1.amazoncognito.com',
    redirectUri: window.location.origin,
    
    // Login via Hosted UI
    login() {
        const loginUrl = `https://${this.domain}/login?` +
            `client_id=${this.clientId}&` +
            `response_type=code&` +
            `scope=email+openid+profile&` +
            `redirect_uri=${encodeURIComponent(this.redirectUri)}`;
        window.location.href = loginUrl;
    },
    
    // Logout
    logout() {
        localStorage.removeItem('id_token');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        
        const logoutUrl = `https://${this.domain}/logout?` +
            `client_id=${this.clientId}&` +
            `logout_uri=${encodeURIComponent(this.redirectUri)}`;
        window.location.href = logoutUrl;
    },
    
    // Exchange authorization code for tokens
    async exchangeCodeForTokens(code) {
        const tokenUrl = `https://${this.domain}/oauth2/token`;
        
        const response = await fetch(tokenUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                grant_type: 'authorization_code',
                client_id: this.clientId,
                code: code,
                redirect_uri: this.redirectUri
            })
        });
        
        const tokens = await response.json();
        
        if (tokens.id_token) {
            localStorage.setItem('id_token', tokens.id_token);
            localStorage.setItem('access_token', tokens.access_token);
            localStorage.setItem('refresh_token', tokens.refresh_token);
        }
        
        return tokens;
    },
    
    // Get current token
    getToken() {
        return localStorage.getItem('id_token');
    },
    
    // Check if user is logged in
    isAuthenticated() {
        const token = this.getToken();
        if (!token) return false;
        
        // Check if token is expired
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.exp * 1000 > Date.now();
    }
};

// Update API client to use tokens
const API = {
    baseUrl: '',
    
    async request(url, options = {}) {
        const token = CognitoAuth.getToken();
        
        if (!token || !CognitoAuth.isAuthenticated()) {
            CognitoAuth.login();
            throw new Error('Not authenticated');
        }
        
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...options.headers
        };
        
        return fetch(url, { ...options, headers });
    },
    
    async emitEvent(eventType, payload) {
        const response = await this.request(`${this.baseUrl}/api/events`, {
            method: 'POST',
            body: JSON.stringify({
                event_type: eventType,
                payload: payload
            })
        });
        
        if (response.status === 401) {
            CognitoAuth.login();
            return;
        }
        
        return response.json();
    }
};

// Handle OAuth callback
window.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    
    if (code) {
        await CognitoAuth.exchangeCodeForTokens(code);
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    // Check authentication
    if (!CognitoAuth.isAuthenticated()) {
        CognitoAuth.login();
    }
});
```

### 6. Update Lambda Environment Variables

In `cloudformation-simple.yaml`, add to Lambda environment:

```yaml
  LambdaFunction:
    Type: AWS::Lambda::Function
    Properties:
      Environment:
        Variables:
          DATABASE_URL: !Sub 'postgresql://${DBMasterUsername}:${DBMasterPassword}@${RDSProxy.Endpoint}:5432/gymapp'
          ANTHROPIC_API_KEY: !Ref AnthropicApiKey
          OPENAI_API_KEY: !Ref OpenAIApiKey
          USE_OPENAI: !Ref UseOpenAI
          COGNITO_REGION: !Ref AWS::Region
          COGNITO_USER_POOL_ID: !Ref UserPool
          COGNITO_CLIENT_ID: !Ref UserPoolClient
```

## Testing

### 1. Create Test User

```bash
# Via AWS CLI
aws cognito-idp admin-create-user \
  --user-pool-id us-west-1_XXXXXXX \
  --username testuser@example.com \
  --user-attributes Name=email,Value=testuser@example.com \
  --temporary-password "TempPass123!" \
  --message-action SUPPRESS

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id us-west-1_XXXXXXX \
  --username testuser@example.com \
  --password "MySecurePass123!" \
  --permanent
```

### 2. Test Authentication Flow

1. Visit your app URL
2. Should redirect to Cognito Hosted UI
3. Login with test user
4. Redirect back with authorization code
5. App exchanges code for tokens
6. API calls include JWT token
7. Lambda verifies token with Cognito

## Cost

- **Free Tier:** 50,000 Monthly Active Users
- **Beyond Free Tier:** $0.0055 per MAU
- **Example:** 10,000 users = FREE

## Security Benefits

- ✅ JWT token verification (no database lookup)
- ✅ Token expiration (1 hour)
- ✅ Refresh tokens (30 days)
- ✅ MFA support
- ✅ Password policies enforced
- ✅ Email verification
- ✅ Password reset flows
- ✅ Account recovery

## Social Login (Optional)

Add to User Pool:

```yaml
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      # ... existing properties ...
      # Add social identity providers
      # Configure in AWS Console after deployment:
      # - Google: OAuth 2.0 client ID & secret
      # - Apple: Service ID, Team ID, Key ID, Private key
      # - Facebook: App ID & secret
```

## Next Steps

1. Deploy CloudFormation with Cognito resources
2. Configure social providers (optional)
3. Customize Hosted UI with your brand (optional)
4. Add user profile management endpoints
5. Consider adding user roles/permissions



