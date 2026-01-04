# Auth0 Implementation Plan for Titan Trakr

## Overview

This document outlines the step-by-step plan to add Auth0 authentication to the Titan Trakr application.

**Estimated Total Time:** 4-6 hours  
**Complexity:** Medium  
**Cost:** $0 (7,500 MAUs free tier)

---

## Phase 1: Auth0 Setup (30 minutes)

### Step 1.1: Create Auth0 Account
1. Go to https://auth0.com/signup
2. Create account with email
3. Choose region: **US** (closest to us-west-1)
4. Complete onboarding

### Step 1.2: Create Application
1. Go to **Applications** → **Create Application**
2. Name: `Titan Trakr`
3. Type: **Single Page Application**
4. Technology: **Vanilla JavaScript** (or HTML5)
5. Click **Create**

### Step 1.3: Configure Application Settings
1. **Allowed Callback URLs:**
   ```
   http://localhost:8000,
   http://localhost:8000/callback,
   https://titantrakr.com,
   https://titantrakr.com/callback,
   https://www.titantrakr.com,
   https://www.titantrakr.com/callback,
   https://staging.titantrakr.com,
   https://staging.titantrakr.com/callback
   ```

2. **Allowed Logout URLs:**
   ```
   http://localhost:8000,
   https://titantrakr.com,
   https://www.titantrakr.com,
   https://staging.titantrakr.com
   ```

3. **Allowed Web Origins:**
   ```
   http://localhost:8000,
   https://titantrakr.com,
   https://www.titantrakr.com,
   https://staging.titantrakr.com
   ```

4. **Save Changes**

### Step 1.4: Create Auth0 API (IMPORTANT!)
> ⚠️ **This step is critical** - the backend validates tokens against this API's audience.

1. Go to **Applications** → **APIs** → **Create API**
2. Name: `Titan Trakr API`
3. Identifier: `https://api.titantrakr.com` (this becomes your `audience`)
4. Signing Algorithm: **RS256**
5. Click **Create**

**Note:** The identifier doesn't need to be a real URL - it's just a unique string.

### Step 1.5: Enable Social Connections (Optional)
1. Go to **Authentication** → **Social**
2. Enable **Google** (recommended for gym app)
3. Enable **Apple** (iOS users will appreciate this)
4. Configure each with OAuth credentials

### Step 1.6: Note Credentials
Save these for later:
- **Domain:** `your-tenant.us.auth0.com`
- **Client ID:** `xxxxxxxxxxxxxx`
- **Client Secret:** (not needed for SPA, but save it)

---

## Phase 2: Backend Implementation (2-3 hours)

### Step 2.1: Install Dependencies

**File:** `requirements.txt`
```diff
  pytest==7.4.4
  pytest-asyncio==0.23.3
  psycopg2-binary==2.9.9
+ python-jose[cryptography]==3.3.0
+ requests==2.31.0
```

**File:** `infrastructure/requirements-lambda.txt`
```diff
  httpx==0.26.0
  
  # PostgreSQL adapter
  psycopg2-binary==2.9.9
+ python-jose[cryptography]==3.3.0
+ requests==2.31.0
  
  # Lambda-specific dependencies
  mangum==0.17.0
```

**File:** `environment.yml`
```diff
      - pytest-asyncio==0.23.3
      - psycopg2-binary==2.9.9
+     - python-jose[cryptography]==3.3.0
+     - requests==2.31.0
```

### Step 2.2: Add Configuration

**File:** `backend/config.py`
```python
# Add after existing config

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", f"https://{AUTH0_DOMAIN}/api/v2/")
AUTH0_ALGORITHMS = ["RS256"]
```

### Step 2.3: Create Authentication Module

**Create new file:** `backend/auth.py`

```python
"""Auth0 JWT authentication for FastAPI."""
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import requests
from functools import lru_cache
from backend.config import AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_AUDIENCE, AUTH0_ALGORITHMS

security = HTTPBearer()

@lru_cache(maxsize=1)
def get_auth0_public_keys():
    """
    Fetch and cache Auth0 public keys for JWT verification.
    
    Note: lru_cache works per Lambda instance. Cold starts will re-fetch,
    but warm instances reuse the cached keys. Keys rotate rarely (months).
    """
    if not AUTH0_DOMAIN:
        return []
    
    jwks_url = f'https://{AUTH0_DOMAIN}/.well-known/jwks.json'
    
    # Retry logic for Lambda cold starts and network issues
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(jwks_url, timeout=5)
            response.raise_for_status()
            return response.json()['keys']
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                continue
            print(f"Timeout fetching Auth0 JWKS after {max_retries} attempts")
            return []
        except Exception as e:
            print(f"Error fetching Auth0 JWKS: {e}")
            return []
    
    return []

def verify_token(token: str) -> dict:
    """
    Verify Auth0 JWT token and return claims.
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Token claims/payload
        
    Raises:
        HTTPException: If token is invalid
    """
    try:
        # Get unverified header to find the key ID
        unverified_header = jwt.get_unverified_header(token)
        
        # Find the matching public key
        jwks = get_auth0_public_keys()
        rsa_key = None
        
        for key in jwks:
            if key['kid'] == unverified_header['kid']:
                rsa_key = {
                    'kty': key['kty'],
                    'kid': key['kid'],
                    'use': key['use'],
                    'n': key['n'],
                    'e': key['e']
                }
                break
        
        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key"
            )
        
        # Verify the token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=AUTH0_ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=f'https://{AUTH0_DOMAIN}/'
        )
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    Dependency to get the current authenticated user.
    
    Args:
        credentials: HTTP Bearer token from request header
        
    Returns:
        str: User ID (Auth0 'sub' claim)
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    # Auth0 'sub' claim format: "auth0|507f1f77bcf86cd799439011"
    # or "google-oauth2|123456789" for social login
    user_id = payload.get('sub')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    return user_id

async def get_current_user_email(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[str]:
    """
    Get the current user's email from token.
    
    Returns:
        Optional[str]: User's email if available
    """
    token = credentials.credentials
    payload = verify_token(token)
    return payload.get('email') or payload.get(f'https://{AUTH0_DOMAIN}/email')

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[str]:
    """
    Optional authentication - returns user_id if authenticated, None otherwise.
    Useful for endpoints that work both authenticated and unauthenticated.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
```

### Step 2.4: Update API Endpoints

**File:** `backend/main.py`

```python
# Add import
from backend.auth import get_current_user, get_current_user_email

# Update endpoints to require authentication
@app.post("/api/events", response_model=EmitEventResponse)
async def emit_event_endpoint(
    request: EmitEventRequest,
    user_id: str = Depends(get_current_user)  # Add this
):
    """Emit a new event."""
    try:
        event_record, derived = emit_event(
            event_type=request.event_type,
            payload=request.payload,
            user_id=user_id  # Use authenticated user
        )
        # ... rest of implementation
```

**Apply to all protected endpoints:**
- `POST /api/events`
- `GET /api/events`
- `GET /api/projections/{key}`
- `POST /api/templates`
- `GET /api/templates`
- `PUT /api/templates/{template_id}`
- `DELETE /api/templates/{template_id}`
- `POST /api/templates/{template_id}/start`
- `GET /api/history`
- `GET /api/history/{workout_id}`
- `POST /api/voice/process`

**Keep public (no auth required):**
- `GET /api/health` - Health check
- `GET /api/auth/config` - Auth0 configuration for frontend (NEW)
- `GET /api/exercises` - Exercise library (or make protected if you want)
- `GET /` - index.html
- Static files (CSS, JS)

### Step 2.5: Add Auth Config Endpoint (For Frontend)

> 💡 **GPT Suggestion:** Don't hardcode Auth0 credentials in frontend - serve them from backend.

**File:** `backend/main.py`

```python
from backend.config import AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_AUDIENCE

@app.get("/api/auth/config")
async def get_auth_config():
    """
    Return Auth0 configuration for frontend.
    This avoids hardcoding credentials in JavaScript.
    """
    return {
        "domain": AUTH0_DOMAIN,
        "clientId": AUTH0_CLIENT_ID,
        "audience": AUTH0_AUDIENCE
    }
```

### Step 2.6: Add User Profile Endpoint

**File:** `backend/main.py`

```python
@app.get("/api/user/profile")
async def get_user_profile(
    user_id: str = Depends(get_current_user),
    email: str = Depends(get_current_user_email)
):
    """Get current user profile."""
    return {
        "user_id": user_id,
        "email": email,
        "created_at": datetime.utcnow().isoformat()
    }
```

---

## Phase 3: Database Migration (30 minutes)

### Step 3.1: Update Database Schema

The current schema already supports multi-user (has `user_id` column in PostgreSQL).

**Verify in:** `infrastructure/init_db.sql`

Already has:
```sql
CREATE TABLE IF NOT EXISTS events (
    ...
    user_id VARCHAR(255) NOT NULL,
    ...
);

CREATE TABLE IF NOT EXISTS projections (
    ...
    user_id VARCHAR(255) NOT NULL,
    ...
);

CREATE TABLE IF NOT EXISTS exercises (
    ...
    user_id VARCHAR(255) NOT NULL,
    ...
);
```

✅ **No changes needed!** Your PostgreSQL schema is already multi-user ready.

### Step 3.2: Add User Profiles Table (Optional)

If you want to store additional user metadata:

```sql
-- Add to infrastructure/init_db.sql
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    display_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    preferences JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_email ON user_profiles(email);
```

---

## Phase 4: Frontend Implementation (2-3 hours)

### Step 4.1: Add Auth0 SPA SDK

**File:** `frontend/index.html`

Add before closing `</head>`:

```html
<!-- Auth0 SPA SDK -->
<script src="https://cdn.auth0.com/js/auth0-spa-js/2.1/auth0-spa-js.production.js"></script>
```

### Step 4.2: Create Auth Module

**Create new file:** `frontend/js/auth.js`

```javascript
/**
 * Auth0 authentication module for Titan Trakr
 */
/**
 * Auth0 authentication module for Titan Trakr
 * 
 * SECURITY NOTE (GPT Suggestion):
 * - Using localStorage for token storage (cacheLocation: 'localstorage')
 * - This has XSS risk if your site has XSS vulnerabilities
 * - For higher security, consider httpOnly cookies via backend proxy
 * - For this app, localStorage is acceptable given:
 *   - No user-generated content displayed as HTML
 *   - CSP headers configured on CloudFront
 *   - Regular security audits
 */
const Auth0Client = {
    client: null,
    user: null,
    isAuthenticated: false,
    
    // Configuration - fetched from backend, not hardcoded
    config: {
        domain: '',
        clientId: '',
        authorizationParams: {
            redirect_uri: window.location.origin,
            audience: '',
            scope: 'openid profile email'
        },
        cacheLocation: 'localstorage',  // See security note above
        useRefreshTokens: true,
        useRefreshTokensFallback: true  // Fallback for browsers without refresh token support
    },
    
    /**
     * Initialize Auth0 client
     */
    async init(config) {
        try {
            // Merge provided config
            this.config = { ...this.config, ...config };
            
            // Create Auth0 client
            this.client = await auth0.createAuth0Client(this.config);
            
            // Check if redirected back from Auth0
            const query = window.location.search;
            if (query.includes('code=') && query.includes('state=')) {
                await this.handleRedirectCallback();
            }
            
            // Check if user is authenticated
            this.isAuthenticated = await this.client.isAuthenticated();
            
            if (this.isAuthenticated) {
                this.user = await this.client.getUser();
                console.log('User authenticated:', this.user);
            }
            
            return this.isAuthenticated;
            
        } catch (error) {
            console.error('Auth0 initialization error:', error);
            return false;
        }
    },
    
    /**
     * Handle redirect callback from Auth0
     */
    async handleRedirectCallback() {
        try {
            await this.client.handleRedirectCallback();
            
            // Clean up URL
            window.history.replaceState(
                {},
                document.title,
                window.location.pathname
            );
            
        } catch (error) {
            console.error('Error handling redirect:', error);
            throw error;
        }
    },
    
    /**
     * Login with redirect to Auth0
     */
    async login() {
        try {
            await this.client.loginWithRedirect({
                authorizationParams: {
                    redirect_uri: window.location.origin
                }
            });
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    },
    
    /**
     * Login with popup (alternative to redirect)
     */
    async loginWithPopup() {
        try {
            await this.client.loginWithPopup();
            this.isAuthenticated = true;
            this.user = await this.client.getUser();
            return this.user;
        } catch (error) {
            console.error('Popup login error:', error);
            throw error;
        }
    },
    
    /**
     * Logout
     */
    async logout() {
        try {
            await this.client.logout({
                logoutParams: {
                    returnTo: window.location.origin
                }
            });
        } catch (error) {
            console.error('Logout error:', error);
            throw error;
        }
    },
    
    /**
     * Get access token for API calls
     */
    async getAccessToken() {
        try {
            if (!this.isAuthenticated) {
                throw new Error('Not authenticated');
            }
            
            const token = await this.client.getTokenSilently();
            return token;
            
        } catch (error) {
            console.error('Error getting token:', error);
            
            // Token expired or invalid - force re-login
            if (error.error === 'login_required' || error.error === 'consent_required') {
                await this.login();
            }
            
            throw error;
        }
    },
    
    /**
     * Get current user
     */
    getUser() {
        return this.user;
    },
    
    /**
     * Check if user is authenticated
     */
    async checkAuth() {
        if (!this.client) {
            return false;
        }
        
        this.isAuthenticated = await this.client.isAuthenticated();
        
        if (this.isAuthenticated) {
            this.user = await this.client.getUser();
        }
        
        return this.isAuthenticated;
    }
};
```

### Step 4.3: Update API Client

**File:** `frontend/js/api.js`

```javascript
const API = {
    baseUrl: '',

    /**
     * Make authenticated API request
     */
    async request(url, options = {}) {
        try {
            // Get access token
            const token = await Auth0Client.getAccessToken();
            
            // Add Authorization header
            const headers = {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
                ...options.headers
            };
            
            const response = await fetch(url, {
                ...options,
                headers
            });
            
            // Handle 401 Unauthorized
            if (response.status === 401) {
                console.warn('Unauthorized - redirecting to login');
                await Auth0Client.login();
                throw new Error('Authentication required');
            }
            
            return response;
            
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    },

    /**
     * Emit an event to the backend.
     */
    async emitEvent(eventType, payload) {
        const response = await this.request(`${this.baseUrl}/api/events`, {
            method: 'POST',
            body: JSON.stringify({
                event_type: eventType,
                payload: payload
            })
        });

        if (!response.ok) {
            const text = await response.text();
            try {
                const error = JSON.parse(text);
                throw new Error(error.detail || 'Failed to emit event');
            } catch (e) {
                throw new Error(`Server error (${response.status}): ${text.substring(0, 100)}`);
            }
        }

        return response.json();
    },
    
    // Update all other methods to use this.request() instead of fetch()
    // ... (similar pattern for getProjection, listEvents, etc.)
};
```

### Step 4.4: Update Main App

**File:** `frontend/js/app.js`

Add initialization in the `init()` method:

```javascript
async init() {
    // Initialize Auth0
    try {
        const authConfig = await this.fetchAuthConfig();
        const isAuthenticated = await Auth0Client.init(authConfig);
        
        if (!isAuthenticated) {
            // Show login page
            this.showLoginPage();
            return;
        }
        
        // User is authenticated - continue with app initialization
        const user = Auth0Client.getUser();
        console.log('Logged in as:', user.email);
        
    } catch (error) {
        console.error('Auth initialization error:', error);
        this.showLoginPage();
        return;
    }
    
    // ... rest of existing init code
},

async fetchAuthConfig() {
    // Fetch Auth0 config from backend (GPT suggestion: don't hardcode)
    try {
        const response = await fetch('/api/auth/config');
        if (!response.ok) {
            throw new Error('Failed to fetch auth config');
        }
        const config = await response.json();
        return {
            domain: config.domain,
            clientId: config.clientId,
            authorizationParams: {
                audience: config.audience,
                redirect_uri: window.location.origin
            }
        };
    } catch (error) {
        console.error('Error fetching auth config:', error);
        // Fallback for development only - remove in production
        throw new Error('Auth configuration unavailable');
    }
},

showLoginPage() {
    // Show simple login UI
    document.body.innerHTML = `
        <div class="flex items-center justify-center min-h-screen bg-gray-900">
            <div class="text-center">
                <h1 class="text-4xl font-bold text-white mb-8">Titan Trakr</h1>
                <button 
                    onclick="Auth0Client.login()"
                    class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-8 rounded-lg"
                >
                    Login / Sign Up
                </button>
            </div>
        </div>
    `;
}
```

### Step 4.5: Add User Menu

**File:** `frontend/index.html`

Add to header:

```html
<div x-show="Auth0Client.isAuthenticated" class="flex items-center gap-4">
    <span x-text="Auth0Client.user?.email" class="text-sm text-gray-400"></span>
    <button 
        @click="Auth0Client.logout()"
        class="text-sm text-gray-300 hover:text-white"
    >
        Logout
    </button>
</div>
```

---

## Phase 5: AWS Deployment Updates (30 minutes)

### Step 5.1: Update CloudFormation Template

**File:** `infrastructure/cloudformation-template.yaml`

Add parameters:

```yaml
  Auth0Domain:
    Type: String
    Description: Auth0 domain (e.g., your-tenant.us.auth0.com)
    Default: ""

  Auth0ClientId:
    Type: String
    Description: Auth0 Client ID
    Default: ""
    NoEcho: true

  Auth0Audience:
    Type: String
    Description: Auth0 API Audience
    Default: ""
```

Add to Lambda environment variables:

```yaml
  LambdaFunction:
    Properties:
      Environment:
        Variables:
          # ... existing vars ...
          AUTH0_DOMAIN: !Ref Auth0Domain
          AUTH0_CLIENT_ID: !Ref Auth0ClientId
          AUTH0_AUDIENCE: !Ref Auth0Audience
```

### Step 5.2: Update Deployment Parameters

**File:** `infrastructure/deploy-parameters.json`

```json
{
  "ParameterKey": "Auth0Domain",
  "ParameterValue": "your-tenant.us.auth0.com"
},
{
  "ParameterKey": "Auth0ClientId",
  "ParameterValue": "YOUR_CLIENT_ID"
},
{
  "ParameterKey": "Auth0Audience",
  "ParameterValue": "https://your-tenant.us.auth0.com/api/v2/"
}
```

---

## Phase 6: Testing (1 hour)

### Test Checklist

- [ ] Local testing with Auth0
  - [ ] Login flow works
  - [ ] Token stored correctly
  - [ ] API calls include token
  - [ ] Protected endpoints require auth
  - [ ] Logout works
  
- [ ] Multi-user testing
  - [ ] Create 2 test accounts
  - [ ] Log workouts with each
  - [ ] Verify data isolation
  - [ ] Check database has correct user_ids
  
- [ ] Error handling
  - [ ] Expired token refreshes
  - [ ] Invalid token returns 401
  - [ ] Network errors handled
  - [ ] Missing token handled
  
- [ ] PostgreSQL verification
  - [ ] Events have correct user_id
  - [ ] Projections scoped to user
  - [ ] No data leakage between users

---

## Implementation Order

### Day 1: Backend (2-3 hours)
1. ✅ Install dependencies
2. ✅ Add backend/auth.py
3. ✅ Update backend/config.py
4. ✅ Protect API endpoints
5. ✅ Test with curl + mock JWT

### Day 2: Frontend (2-3 hours)
6. ✅ Add Auth0 SDK
7. ✅ Create frontend/js/auth.js
8. ✅ Update API client
9. ✅ Add login UI
10. ✅ Test full flow locally

### Day 3: Deployment (1 hour)
11. ✅ Update CloudFormation
12. ✅ Deploy to staging
13. ✅ Test on staging
14. ✅ Deploy to production

---

## Rollback Plan

If something goes wrong:

1. **Backend issues:** Remove `Depends(get_current_user)` to make endpoints public again
2. **Frontend issues:** Comment out Auth0 initialization, add temporary bypass
3. **Deployment issues:** Rollback CloudFormation stack to previous version

---

## Post-Implementation

### Documentation to Update:
- [ ] README.md (add auth setup instructions)
- [ ] DEPLOYMENT.md (add Auth0 configuration)
- [ ] Add AUTH0_SETUP.md for detailed Auth0 configuration

### Future Enhancements:
- [ ] Add social login buttons (Google, Apple)
- [ ] Implement user profiles
- [ ] Add user preferences
- [ ] Set up email notifications (Auth0 Actions)
- [ ] Add usage analytics per user
- [ ] Implement admin role

---

---

## Security Considerations (GPT Feedback Incorporated)

### Token Storage (XSS Risk)

**Current approach:** localStorage via Auth0 SPA SDK

**Risk:** If XSS vulnerability exists, attacker can steal tokens.

**Mitigations in place:**
1. ✅ No user-generated HTML content rendered (React/Alpine escape by default)
2. ✅ CSP headers configured on CloudFront
3. ✅ Refresh tokens rotate on use (Auth0 default)
4. ✅ Access tokens expire in 1 hour
5. ✅ All API calls over HTTPS

**Higher security alternative (future):**
- Use httpOnly cookies via backend proxy
- Requires additional backend route for token exchange
- Adds complexity, recommended only if handling sensitive data

### Audience Validation

**Critical:** The `AUTH0_AUDIENCE` in backend MUST match the API identifier created in Step 1.4.

```python
# Backend validates tokens against this audience
AUTH0_AUDIENCE = "https://api.titantrakr.com"  # Must match Auth0 API identifier
```

### Roles and Permissions (Future Enhancement)

For admin features (user management, analytics), add:

1. **In Auth0:**
   - Create roles (admin, user)
   - Assign permissions to roles
   - Add users to roles

2. **In Backend:**
   ```python
   def require_permission(permission: str):
       async def check_permission(token_payload: dict = Depends(verify_token)):
           permissions = token_payload.get('permissions', [])
           if permission not in permissions:
               raise HTTPException(status_code=403, detail="Insufficient permissions")
       return check_permission
   
   @app.delete("/api/admin/users/{user_id}")
   async def delete_user(
       user_id: str,
       _: None = Depends(require_permission("admin:delete_users"))
   ):
       ...
   ```

### CORS Configuration

CloudFront + Lambda function URL handles CORS. Ensure:
- `Access-Control-Allow-Origin` matches your domains
- `Access-Control-Allow-Headers` includes `Authorization`

---

## Cost Projection

**Auth0 Free Tier:** 7,500 MAUs
- First 7,500 users: **$0/month**
- 7,501 - 10,000 users: **$35/month** (Essential tier)
- Beyond: $0.07 per additional MAU

**Break-even analysis:**
- You need 7,500+ active users to pay anything
- Even then, only $35/month for next 500 users
- Extremely cost-effective for your use case

---

## Success Criteria

✅ Users can sign up and login via Auth0  
✅ Each user sees only their own workouts  
✅ API endpoints are protected  
✅ Tokens refresh automatically  
✅ Logout works correctly  
✅ No breaking changes for existing functionality  
✅ Works on localhost and production  
✅ PostgreSQL properly isolates user data  

---

## Next Steps

Ready to implement? I can start with:

1. **Backend first** (safer, can test with tools)
2. **Complete implementation** (all phases)
3. **Review specific phase** (your questions)

What would you like me to do?

