import axios from 'axios';
import { getCurrentUser } from './auth';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

function getToken() {
  const user = getCurrentUser();
  return user ? user.token : null;
}

export async function fetchCourses() {
  const res = await axios.get(`${API_BASE}/courses`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
}

export async function createCourse({name, description}) {
  const res = await axios.post(`${API_BASE}/courses`, {name, description}, {
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

export async function saveCourseSettings(courseId, settings) {
  
  const res = await axios.put(`${API_BASE}/courses/${courseId}/settings`, settings, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
}

export async function getCourseSettings(courseId) {
  const res = await axios.get(`${API_BASE}/courses/${courseId}/settings`, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  return res.data;
} 