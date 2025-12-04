/**
 * Keycloak authentication service for React
 * Replaces Firebase auth with Keycloak login
 */
import Keycloak from 'keycloak-js';

// Keycloak configuration from environment variables
const keycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL || 'http://localhost:8080',
  realm: process.env.REACT_APP_KEYCLOAK_REALM || 'CourseCopilot',
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'course-copilot-frontend',
};

// Initialize Keycloak instance
const keycloak = new Keycloak(keycloakConfig);
let keycloakInitialized = false;
let keycloakInitPromise = null;

/**
 * Initialize Keycloak and attempt SSO login
 * Returns promise that resolves when authenticated
 */
export async function initKeycloak({ forceReload = false } = {}) {
  // If already initialized (and not forcing), reuse existing state/promise
  if (keycloakInitialized && !forceReload) {
    return keycloak.authenticated ?? false;
  }
  if (keycloakInitPromise && !forceReload) {
    return keycloakInitPromise;
  }

  // Check if we have an authorization code in the URL (OAuth callback)
  const urlParams = new URLSearchParams(window.location.search);
  const hasCode = urlParams.has('code');

  // If we have a code, we're returning from Keycloak login
  // Use 'login-required' to process the callback
  // Otherwise, use 'check-sso' to check if already logged in
  const onLoadOption = hasCode ? 'login-required' : 'check-sso';

  console.log('Initializing Keycloak...', { onLoad: onLoadOption, hasCode, forceReload });

  keycloakInitPromise = keycloak
    .init({
      onLoad: onLoadOption,
      silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
      pkceMethod: 'S256', // Use PKCE for security
      checkLoginIframe: false,
    })
    .then(async (authenticated) => {
      keycloakInitialized = true;

      if (authenticated) {
        // User is authenticated (either from callback or already logged in)
        await updateLocalStorage();

        // Clean up the URL if we had a code
        if (hasCode) {
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      }

      return authenticated;
    })
    .catch((error) => {
      keycloakInitialized = false;
      console.error('Keycloak initialization failed:', error);
      return false;
    })
    .finally(() => {
      keycloakInitPromise = null;
    });

  return keycloakInitPromise;
}

/**
 * Login user - redirects to Keycloak login page
 */
export async function loginKeycloak() {
  const redirectUri = window.location.origin + '/dashboard';
  console.log('Attempting Keycloak login...', {
    url: keycloakConfig.url,
    realm: keycloakConfig.realm,
    clientId: keycloakConfig.clientId,
    redirectUri: redirectUri
  });
  
  try {
    // Use keycloak.login() - this is the preferred method as it handles the OAuth flow properly
    keycloak.login({
      redirectUri: redirectUri,
    });
    
    // If keycloak.login() doesn't redirect (shouldn't happen, but just in case)
    // Use fallback after a short delay
    setTimeout(() => {
      console.warn('keycloak.login() did not redirect, using fallback...');
      const encodedRedirect = encodeURIComponent(redirectUri);
      const loginUrl = `${keycloakConfig.url}/realms/${keycloakConfig.realm}/protocol/openid-connect/auth?client_id=${keycloakConfig.clientId}&redirect_uri=${encodedRedirect}&response_type=code&scope=openid`;
      window.location.href = loginUrl;
    }, 100);
  } catch (error) {
    console.error('keycloak.login() failed, using direct redirect:', error);
    // Fallback: direct redirect
    const encodedRedirect = encodeURIComponent(redirectUri);
    const loginUrl = `${keycloakConfig.url}/realms/${keycloakConfig.realm}/protocol/openid-connect/auth?client_id=${keycloakConfig.clientId}&redirect_uri=${encodedRedirect}&response_type=code&scope=openid`;
    window.location.href = loginUrl;
  }
}

/**
 * Logout user
 */
export async function logoutKeycloak() {
  try {
    // Make sure Keycloak is initialized so logout knows the current session
    if (!keycloakInitialized) {
      try {
        await initKeycloak();
      } catch (initError) {
        console.warn('Keycloak was not initialized before logout:', initError);
      }
    }

    await keycloak.logout({
      redirectUri: window.location.origin + '/login',
    });
  } catch (error) {
    console.error('Keycloak logout failed:', error);
  } finally {
    // Always clear local auth state on logout attempt
    keycloak.clearToken?.();
    keycloakInitialized = false;
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
  }
}

/**
 * Get current user info from Keycloak token
 */
export function getKeycloakUser() {
  if (!keycloak.authenticated) {
    return null;
  }

  try {
    const tokenParsed = keycloak.tokenParsed;
    if (!tokenParsed) {
      return null;
    }

    return {
      id: tokenParsed.sub, // User ID
      email: tokenParsed.email || tokenParsed.preferred_username,
      name: tokenParsed.name || tokenParsed.preferred_username,
      roles: tokenParsed.realm_access?.roles || [],
      displayName: tokenParsed.name || tokenParsed.preferred_username || tokenParsed.email,
    };
  } catch (error) {
    console.error('Error parsing Keycloak token:', error);
    return null;
  }
}

/**
 * Get access token for API calls
 */
export function getKeycloakToken() {
  return keycloak.token;
}

/**
 * Check if user is authenticated
 */
export function isKeycloakAuthenticated() {
  return keycloak.authenticated === true;
}

/**
 * Check if user has a specific role
 */
export function hasKeycloakRole(role) {
  if (!keycloak.authenticated) {
    return false;
  }
  
  const tokenParsed = keycloak.tokenParsed;
  if (!tokenParsed) {
    return false;
  }
  
  const roles = tokenParsed.realm_access?.roles || [];
  return roles.includes(role);
}

/**
 * Update localStorage with Keycloak user info and token
 * (Maintains compatibility with existing code)
 */
async function updateLocalStorage() {
  const user = getKeycloakUser();
  const token = getKeycloakToken();

  if (user && token) {
    // Store in same format as Firebase for compatibility
    localStorage.setItem('user', JSON.stringify({
      id: user.id,
      email: user.email,
      displayName: user.displayName,
      token: token,
      roles: user.roles,
    }));
    localStorage.setItem('token', token);
    
    // Keycloak doesn't have refresh_token in the same way, but we can store it
    if (keycloak.refreshToken) {
      localStorage.setItem('refresh_token', keycloak.refreshToken);
    }
  }
}

/**
 * Setup token refresh - automatically refresh token before it expires
 */
export function setupTokenRefresh() {
  keycloak.onTokenExpired = () => {
    keycloak.updateToken(30) // Refresh token when it's about to expire (30 seconds before)
      .then((refreshed) => {
        if (refreshed) {
          console.log('Token refreshed');
          updateLocalStorage();
        }
      })
      .catch((error) => {
        console.error('Token refresh failed:', error);
        // Redirect to login if refresh fails
        logoutKeycloak();
      });
  };
}

// Export keycloak instance for advanced use cases
export { keycloak };

