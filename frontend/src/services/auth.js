import { API_BASE } from '../utils/axiosConfig';
import axios from 'axios';

export async function login(email, password) {
  try {
    // Use raw axios for login (not the instance with interceptor to avoid infinite loop)
    const response = await axios.post(`${API_BASE}/login`, { email, password });
    
    // Create user object from backend response
    const userData = {
      id: response.data.user_id,
      email: email,
      token: response.data.token,
      message: response.data.message
    };
    
    localStorage.setItem('user', JSON.stringify(userData));
    localStorage.setItem('token', response.data.token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    return userData;
  } catch (error) {
    throw error.response?.data || { detail: 'Login failed' };
  }
}

export async function googleLogin() {
  try {
    // Use raw axios for google login (not the instance with interceptor)
    const response = await axios.get(`${API_BASE}/google-login`);
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Google login failed' };
  }
}

export async function register(email, password, name) {
  try {
    // Use raw axios for registration (not the instance with interceptor)
    const response = await axios.post(`${API_BASE}/signup`, { email, password, name });
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Registration failed' };
  }
}

export function logout() {
  localStorage.removeItem('user');
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
}

export function getCurrentUser() {
  const user = localStorage.getItem('user');
  return user ? JSON.parse(user) : null;
}

export function getAuthToken() {
  const user = getCurrentUser();
  return user ? user.token : null;
}

export function isAuthenticated() {
  return !!getAuthToken();
}

// Seconds left on a JWT, or null if it carries no readable `exp`.
// Firebase ID tokens are JWTs; this only READS the unverified payload to decide
// whether to bother navigating. The signature is verified server-side only.
function tokenSecondsRemaining(token) {
  try {
    const payload = JSON.parse(
      atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))
    );
    if (!payload || typeof payload.exp !== 'number') return null;
    return payload.exp - Math.floor(Date.now() / 1000);
  } catch {
    return null;
  }
}

/**
 * True when the stored credentials can still result in authenticated API calls.
 *
 * Stricter than isAuthenticated(): a token that has already expired does not
 * count unless a refresh_token is present, in which case the axios interceptor
 * will silently renew it on the first request. A malformed token with no
 * readable `exp` is accepted only if it looks like a JWT at all.
 */
export function hasUsableSession() {
  const token = getAuthToken();
  if (!token) return false;

  const remaining = tokenSecondsRemaining(token);
  if (remaining === null) {
    // Not a decodable JWT — let the backend be the judge, but only if it is at
    // least shaped like one. A junk value means a tampered-with localStorage.
    return token.split('.').length === 3;
  }

  // Treat "about to expire" as expired so we don't flash a page that instantly 401s.
  if (remaining > 30) return true;

  return !!localStorage.getItem('refresh_token');
}

export function getUserId() {
  const user = getCurrentUser();
  return user ? user.id : null;
}

export function getUserEmail() {
  const user = getCurrentUser();
  return user ? user.email : null;
}

export function getUserDisplayName() {
  const user = getCurrentUser();
  return user ? user.displayName : null;
}
