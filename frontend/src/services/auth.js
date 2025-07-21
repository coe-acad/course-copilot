// API base URL - adjust this to match your backend URL
const API_BASE_URL = 'http://localhost:8000';

// Helper function to make API calls
async function apiCall(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// Login with email and password
export async function login(email, password) {
  try {
    const response = await apiCall('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    // Store the Firebase ID token
    localStorage.setItem('authToken', response.token);
    localStorage.setItem('user', JSON.stringify({ 
      id: response.user_id, 
      email: email 
    }));

    return { success: true, user: { id: response.user_id, email } };
  } catch (error) {
    console.error('Login failed:', error);
    return { success: false, error: error.message };
  }
}

// Register new user
export async function register(email, password, name) {
  try {
    await apiCall('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password, name }),
    });

    // After successful signup, automatically log in
    const loginResult = await login(email, password);
    return loginResult;
  } catch (error) {
    console.error('Registration failed:', error);
    return { success: false, error: error.message };
  }
}

// Logout - now calls backend
export async function logout() {
  try {
    const token = localStorage.getItem('authToken');
    
    if (token) {
      // Call backend logout endpoint
      await apiCall('/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
    }
  } catch (error) {
    console.error('Backend logout failed:', error);
    // Continue with client-side cleanup even if backend fails
  } finally {
    // Always clear local storage
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    localStorage.removeItem('currentCourseTitle');
    localStorage.removeItem('currentCourseId');
  }
}

// Get current user
export function getCurrentUser() {
  const user = localStorage.getItem('user');
  const token = localStorage.getItem('authToken');
  
  if (user && token) {
    return JSON.parse(user);
  }
  return null;
}

// Get auth token for API calls
export function getAuthToken() {
  return localStorage.getItem('authToken');
}

// Check if user is authenticated
export function isAuthenticated() {
  return !!getAuthToken();
}

// Google OAuth login
export function startGoogleLogin() {
  // Redirect to backend's Google OAuth endpoint
  window.location.href = `${API_BASE_URL}/auth/google-login`;
}

// Verify token validity (optional - call this periodically)
export async function verifyToken() {
  try {
    const token = getAuthToken();
    if (!token) return false;

    // You can add a token verification endpoint to your backend
    // For now, we'll just check if token exists
    return true;
  } catch (error) {
    console.error('Token verification failed:', error);
    logout();
    return false;
  }
}