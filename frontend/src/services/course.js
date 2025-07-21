// Course service for API calls to backend
const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000/api';

// Helper to get the Firebase token from localStorage
function getAuthToken() {
  return localStorage.getItem('authToken');
}

// Helper function to make authenticated API calls
async function apiCall(endpoint, options = {}) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('No authentication token found');
  }

  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
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

export async function fetchCourses() {
  try {
    const courses = await apiCall('/courses');
    return courses;
  } catch (error) {
    console.error('Failed to fetch courses:', error);
    throw error;
  }
}

export async function createCourse({ name, description, year, level }) {
  try {
    const courseData = await apiCall('/courses', {
      method: 'POST',
      body: JSON.stringify({ 
        name, 
        description, 
        year: year || 2024, 
        level: level || "Beginner" 
      }),
    });
    return courseData;
  } catch (error) {
    console.error('Failed to create course:', error);
    throw error;
  }
}

export async function updateCourse(courseId, { name, description, archived }) {
  try {
    const courseData = await apiCall(`/courses/${courseId}`, {
      method: 'PUT',
      body: JSON.stringify({ name, description, archived }),
    });
    return courseData;
  } catch (error) {
    console.error('Failed to update course:', error);
    throw error;
  }
}

export async function deleteCourse(courseId) {
  try {
    const result = await apiCall(`/courses/${courseId}`, {
      method: 'DELETE',
    });
    return result;
  } catch (error) {
    console.error('Failed to delete course:', error);
    throw error;
  }
}

export async function getCourse(courseId) {
  try {
    const course = await apiCall(`/courses/${courseId}`);
    return course;
  } catch (error) {
    console.error('Failed to fetch course:', error);
    throw error;
  }
} 