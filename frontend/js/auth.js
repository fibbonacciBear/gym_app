/**
 * Auth0 authentication integration.
 * 
 * This module handles:
 * - Auth0 SDK initialization
 * - Login/Logout flows
 * - Token management
 * - User profile retrieval
 */

let auth0Client = null;
let authConfig = null;

/**
 * Initialize Auth0 client with configuration from backend.
 */
async function initAuth0() {
    try {
        // Fetch Auth0 configuration from backend
        const response = await fetch('/api/auth/config');
        if (!response.ok) {
            throw new Error('Failed to fetch Auth0 configuration');
        }
        
        authConfig = await response.json();
        
        // Validate configuration
        if (!authConfig.domain || !authConfig.clientId || !authConfig.audience) {
            console.warn('Auth0 configuration incomplete. Authentication will be unavailable.');
            return false;
        }
        
        // Initialize Auth0 client
        auth0Client = await auth0.createAuth0Client({
            domain: authConfig.domain,
            clientId: authConfig.clientId,
            authorizationParams: {
                redirect_uri: window.location.origin,
                audience: authConfig.audience,
                scope: 'openid profile email'
            },
            cacheLocation: 'localstorage',
            useRefreshTokens: true
        });
        
        // Check if returning from Auth0 redirect
        if (window.location.search.includes('code=') && window.location.search.includes('state=')) {
            try {
                await auth0Client.handleRedirectCallback();
                // Clean up URL
                window.history.replaceState({}, document.title, window.location.pathname);
            } catch (error) {
                console.error('Error handling redirect callback:', error);
            }
        }
        
        return true;
    } catch (error) {
        console.error('Failed to initialize Auth0:', error);
        return false;
    }
}

/**
 * Check if user is authenticated.
 */
async function isAuthenticated() {
    if (!auth0Client) return false;
    try {
        return await auth0Client.isAuthenticated();
    } catch (error) {
        console.error('Error checking authentication:', error);
        return false;
    }
}

/**
 * Get the current authenticated user.
 */
async function getUser() {
    if (!auth0Client) return null;
    try {
        return await auth0Client.getUser();
    } catch (error) {
        console.error('Error getting user:', error);
        return null;
    }
}

/**
 * Get an access token for API requests.
 * Returns null if not authenticated.
 */
async function getAccessToken() {
    if (!auth0Client) return null;
    try {
        const authenticated = await auth0Client.isAuthenticated();
        if (!authenticated) return null;
        
        return await auth0Client.getTokenSilently({
            authorizationParams: {
                audience: authConfig.audience
            }
        });
    } catch (error) {
        console.error('Error getting access token:', error);
        // If token refresh fails, user needs to login again
        if (error.error === 'login_required') {
            return null;
        }
        throw error;
    }
}

/**
 * Initiate login flow.
 */
async function login() {
    if (!auth0Client) {
        console.error('Auth0 client not initialized');
        return;
    }
    
    try {
        await auth0Client.loginWithRedirect({
            authorizationParams: {
                redirect_uri: window.location.origin,
                audience: authConfig.audience,
                scope: 'openid profile email'
            }
        });
    } catch (error) {
        console.error('Login error:', error);
        throw error;
    }
}

/**
 * Logout the current user.
 */
async function logout() {
    if (!auth0Client) {
        console.error('Auth0 client not initialized');
        return;
    }
    
    try {
        await auth0Client.logout({
            logoutParams: {
                returnTo: window.location.origin
            }
        });
    } catch (error) {
        console.error('Logout error:', error);
        throw error;
    }
}

// Export functions for use in other modules
window.Auth = {
    init: initAuth0,
    isAuthenticated,
    getUser,
    getAccessToken,
    login,
    logout
};



