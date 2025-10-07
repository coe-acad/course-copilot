// LMS Service - Handles all LMS platform operations
import axios from 'axios';

const baseUrl = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
const API_BASE = new URL('/api', baseUrl).toString();

/**
 * Get user authentication token
 */
function getUserToken() {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  if (!user.token) {
    throw new Error('User not authenticated. Please log in.');
  }
  return user.token;
}

/**
 * Get LMS authentication cookies (session-based auth)
 */
function getLMSCookies() {
  const lmsCookies = localStorage.getItem('lms_cookies');
  if (!lmsCookies) {
    throw new Error('Not logged into LMS. Please login to LMS first.');
  }
  return lmsCookies;
}

/**
 * Login to LMS platform
 * @param {string} email - LMS user email
 * @param {string} password - LMS user password
 * @returns {Promise<Object>} Login response with token and user info
 */
export async function loginToLMS(email, password) {
  try {
    const response = await axios.post(
      `${API_BASE}/login-lms`,
      { email, password },
      {
        headers: {
          'Authorization': `Bearer ${getUserToken()}`,
          'Content-Type': 'application/json'
        }
      }
    );

    // Store LMS credentials in localStorage
    const lmsCookies = response.data.cookies || "";
    const lmsToken = response.data.token || response.data.data?.token || "";
    const lmsUser = response.data.data?.user || response.data.user || {};
    
    localStorage.setItem("lms_cookies", lmsCookies);
    localStorage.setItem("lms_user", JSON.stringify(lmsUser));
    if (lmsToken) {
      localStorage.setItem("lms_token", lmsToken);  // Store token if provided
    }
    
    return {
      success: true,
      cookies: lmsCookies,
      token: lmsToken,
      user: lmsUser,
      message: response.data.message
    };
  } catch (error) {
    console.error('LMS login error:', error);
    throw error.response?.data || { detail: 'LMS login failed' };
  }
}

/**
 * Get courses from LMS platform
 * @returns {Promise<Array>} List of LMS courses
 */
export async function getLMSCourses() {
  try {
    const lmsCookies = getLMSCookies();
    const userToken = getUserToken();

    const response = await axios.post(
      `${API_BASE}/courses-lms`,
      { lms_cookies: lmsCookies },
      {
        headers: {
          'Authorization': `Bearer ${userToken}`,
          'Content-Type': 'application/json'
        }
      }
    );

    return {
      success: true,
      courses: response.data.data || [],
      message: response.data.message
    };
  } catch (error) {
    console.error('Get LMS courses error:', error);
    
    // If cookies expired or invalid, clear LMS data
    if (error.response?.status === 401 || error.response?.status === 403) {
      localStorage.removeItem('lms_cookies');
      localStorage.removeItem('lms_token');
      localStorage.removeItem('lms_user');
    }
    
    throw error.response?.data || { detail: 'Failed to fetch LMS courses' };
  }
}

/**
 * Check if user is logged into LMS
 * @returns {boolean}
 */
export function isLoggedIntoLMS() {
  const lmsCookies = localStorage.getItem('lms_cookies');
  return !!lmsCookies;
}

/**
 * Logout from LMS
 */
export function logoutFromLMS() {
  localStorage.removeItem('lms_cookies');
  localStorage.removeItem('lms_token');
  localStorage.removeItem('lms_user');
  localStorage.removeItem('lms_courses');
}

/**
 * Get LMS user info
 * @returns {Object|null}
 */
export function getLMSUser() {
  const lmsUserStr = localStorage.getItem('lms_user');
  return lmsUserStr ? JSON.parse(lmsUserStr) : null;
}

/**
 * Get stored LMS courses from localStorage
 * @returns {Array} List of courses (empty array if none stored)
 */
export function getStoredLMSCourses() {
  const coursesStr = localStorage.getItem('lms_courses');
  return coursesStr ? JSON.parse(coursesStr) : [];
}

/**
 * Clear stored LMS courses
 */
export function clearStoredLMSCourses() {
  localStorage.removeItem('lms_courses');
}

// Export default object with all functions
export default {
  loginToLMS,
  getLMSCourses,
  isLoggedIntoLMS,
  logoutFromLMS,
  getLMSUser,
  getStoredLMSCourses,
  clearStoredLMSCourses
};

