import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

function getToken() {
  return localStorage.getItem('token');
}

export async function fetchCourses(user_id = 123) {
  const res = await axios.get(`${API_BASE}/courses?user_id=${user_id}`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
}

export async function createCourse({name, description, user_id = 123}) {
  const res = await axios.post(`${API_BASE}/courses?user_id=${user_id}`, {name, description}, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`
    }
  });
  return res.data;
}

export async function deleteCourse(courseId) {
  const res = await axios.delete(`${API_BASE}/courses/${courseId}`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
}

export async function getCourse(courseId) {
  const res = await axios.get(`${API_BASE}/courses/${courseId}`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
}

export async function saveCourseSettings(courseId, settings, user_id = 123) {
  const res = await axios.put(`${API_BASE}/courses/${courseId}/settings?user_id=${user_id}`, settings, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
}

export async function getCourseSettings(courseId, user_id = 123) {
  const res = await axios.get(`${API_BASE}/courses/${courseId}/settings?user_id=${user_id}`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
} 