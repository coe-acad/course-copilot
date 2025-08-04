import axios from 'axios';
import { getCurrentUser } from './auth';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

function getToken() {
  const user = getCurrentUser();
  if (!user || !user.token) {
    throw new Error('User not authenticated. Please log in.');
  }
  return user.token;
}


export async function getAllResources(courseId = null) {
  // If courseId is not provided, try to get it from localStorage
  if (!courseId) {
    courseId = localStorage.getItem('currentCourseId');
    if (!courseId) {
      throw new Error('No course ID provided and none found in localStorage');
    }
  }
  
  const res = await axios.get(`${API_BASE}/courses/${courseId}/resources`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
}

// upload resources
export async function uploadResources(courseId, files) {
  const res = await axios.post(`${API_BASE}/courses/${courseId}/resources`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
}


function handleAxiosError(error) {
  if (error.response && error.response.data && error.response.data.detail) {
    throw new Error(error.response.data.detail);
  }
  throw new Error(error.message || 'Unknown error');
}

export async function uploadCourseResources(courseId, files) {
  console.log('uploadCourseResources called with:', { courseId, filesCount: files.length });
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  try {
    const res = await axios.post(`${API_BASE}/courses/${courseId}/resources`, formData, {
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    console.log('Upload response:', res.data);
    return res.data;
  } catch (error) {
    console.error('Upload error:', error);
    handleAxiosError(error);
  }
}