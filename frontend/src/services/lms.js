// LMS Service - Handles all LMS platform operations
import axiosInstance from '../utils/axiosConfig';

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
    const response = await axiosInstance.post(
      '/login-lms',
      { email, password }
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

    const response = await axiosInstance.post(
      '/courses-lms',
      { lms_cookies: lmsCookies }
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
 * Create a new module in LMS platform
 * @param {string} lmsCourseId - LMS course ID
 * @param {string} moduleTitle - Title of the module
 * @param {number} order - Order of the module (defaults to 1)
 * @returns {Promise<Object>} Response with created module data
 */
export async function createLMSModule(lmsCourseId, moduleTitle, order = 1) {
  try {
    const lmsCookies = getLMSCookies();

    const response = await axiosInstance.post(
      '/create-module-lms',
      { 
        lms_cookies: lmsCookies,
        lms_course_id: lmsCourseId,
        module_title: moduleTitle,
        order: order
      }
    );

    return {
      success: true,
      module: response.data.data || {},
      message: response.data.message
    };
  } catch (error) {
    console.error('Create LMS module error:', error);
    
    // If cookies expired or invalid, clear LMS data
    if (error.response?.status === 401 || error.response?.status === 403) {
      localStorage.removeItem('lms_cookies');
      localStorage.removeItem('lms_token');
      localStorage.removeItem('lms_user');
    }
    
    throw error.response?.data || { detail: 'Failed to create LMS module' };
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
  createLMSModule,
  isLoggedIntoLMS,
  logoutFromLMS,
  getLMSUser,
  getStoredLMSCourses,
  clearStoredLMSCourses
};

