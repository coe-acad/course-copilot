import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

export async function login(email, password) {
  try {
    const response = await axios.post(`${API_BASE}/auth/login`, { email, password });
    localStorage.setItem('user', JSON.stringify(response.data));
    localStorage.setItem('token', response.data.token); // Store token for authenticated requests
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Login failed' };
  }
}

export async function register(email, password, name) {
  try {
    const response = await axios.post(`${API_BASE}/auth/signup`, { email, password, name });
    return response.data;
  } catch (error) {
    throw error.response?.data || { detail: 'Registration failed' };
  }
}

export function logout() {
  localStorage.removeItem('user');
  localStorage.removeItem('token');
  // Optionally, call backend logout endpoint if needed
}

export function getCurrentUser() {
  const user = localStorage.getItem('user');
  return user ? JSON.parse(user) : null;
}
