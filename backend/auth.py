"""Auth0 JWT authentication for FastAPI."""
from typing import Optional
from fastapi import Security, HTTPException, status, Depends, Header
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
    
    Includes retry logic per GPT's suggestion for Lambda cold starts.
    """
    if not AUTH0_DOMAIN:
        print("Warning: AUTH0_DOMAIN not configured")
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
                print(f"Timeout fetching Auth0 JWKS, attempt {attempt + 1}/{max_retries}")
                continue
            print(f"Timeout fetching Auth0 JWKS after {max_retries} attempts")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Auth0 JWKS: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error fetching Auth0 JWKS: {e}")
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
    if not AUTH0_DOMAIN or not AUTH0_AUDIENCE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 not configured"
        )
    
    try:
        # Get unverified header to find the key ID
        unverified_header = jwt.get_unverified_header(token)
        
        # Find the matching public key
        jwks = get_auth0_public_keys()
        if not jwks:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to fetch Auth0 public keys"
            )
        
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
        # GPT Note: Ensure AUTH0_AUDIENCE matches API identifier exactly (no trailing slash)
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
        
    Examples:
        - "auth0|507f1f77bcf86cd799439011" (Auth0 database)
        - "google-oauth2|123456789" (Google social login)
        - "apple|000123.abc.def" (Apple social login)
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    # Auth0 'sub' claim is the unique user identifier
    user_id = payload.get('sub')
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload - missing 'sub' claim"
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
    
    # Try standard 'email' claim first
    email = payload.get('email')
    if email:
        return email
    
    # Fallback to namespaced claim (if using custom rules)
    namespaced_email = payload.get(f'https://{AUTH0_DOMAIN}/email')
    return namespaced_email

async def get_current_user_optional(
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    """
    Optional authentication - returns user_id if authenticated, None otherwise.

    Useful for endpoints that work both authenticated and unauthenticated.
    For example: public exercise library that shows personalized data if logged in.
    
    Note: Uses Header dependency to make Authorization optional.
    """
    if not authorization:
        return None
    
    # Extract token from "Bearer <token>"
    if not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = verify_token(token)
        user_id = payload.get('sub')
        return user_id if user_id else None
    except Exception:
        # Invalid token - return None to allow unauthenticated access
        return None

