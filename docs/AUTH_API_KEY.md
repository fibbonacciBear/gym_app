# API Key Authentication Implementation

## Overview
Simple API key-based authentication for controlled access.

## Implementation Steps

### 1. Add API Key Table to Database

```sql
-- Add to infrastructure/init_db.sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    api_key VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_users_api_key ON users(api_key);
```

### 2. Add Authentication Middleware

```python
# backend/auth.py
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from backend.database import get_connection

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_current_user(api_key: str = Security(api_key_header)) -> str:
    """Validate API key and return user_id."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key"
        )
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, is_active FROM users WHERE api_key = %s",
                (api_key,)
            )
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API Key"
                )
            
            user_id, is_active = result
            
            if not is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is disabled"
                )
            
            return user_id
```

### 3. Protect Endpoints

```python
# backend/main.py
from backend.auth import get_current_user

@app.post("/api/events")
async def emit_event_endpoint(
    request: EmitEventRequest,
    user_id: str = Depends(get_current_user)  # Add this
):
    # Now user_id comes from the API key, not hardcoded "default"
    event_record, derived = emit_event(
        event_type=request.event_type,
        payload=request.payload,
        user_id=user_id  # Use authenticated user
    )
    ...
```

### 4. User Management Script

```python
# scripts/manage_users.py
import secrets
import sys
from backend.database import get_connection

def create_user(email: str) -> str:
    """Create a new user with API key."""
    user_id = email.split('@')[0]  # Simple user_id from email
    api_key = secrets.token_urlsafe(32)
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (user_id, api_key, email) VALUES (%s, %s, %s)",
                (user_id, api_key, email)
            )
        conn.commit()
    
    return api_key

if __name__ == "__main__":
    email = sys.argv[1]
    api_key = create_user(email)
    print(f"Created user: {email}")
    print(f"API Key: {api_key}")
    print(f"\nUse in requests:")
    print(f"curl -H 'X-API-Key: {api_key}' http://localhost:8000/api/...")
```

### 5. Frontend Changes

```javascript
// frontend/js/api.js
const API = {
    baseUrl: '',
    apiKey: localStorage.getItem('api_key') || '',
    
    setApiKey(key) {
        this.apiKey = key;
        localStorage.setItem('api_key', key);
    },
    
    async emitEvent(eventType, payload) {
        const headers = {
            'Content-Type': 'application/json',
        };
        
        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }
        
        const response = await fetch(`${this.baseUrl}/api/events`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                event_type: eventType,
                payload: payload
            })
        });
        
        if (response.status === 401) {
            // Redirect to login or show API key input
            alert('Please enter your API key');
            return;
        }
        
        return response.json();
    }
}
```

## Usage

```bash
# Create a user
python scripts/manage_users.py user@example.com

# Output:
# Created user: user@example.com
# API Key: Zxc9_KmN8pQrStUvWxYz-AbCdEfGhIjKlMnO
```

## Cost
- $0 (just database storage)

## Security Notes
- API keys don't expire (consider adding expiration)
- Use HTTPS only (enforced by CloudFront)
- Store keys securely in environment variables for CI/CD
- Consider rate limiting per API key



