import axios from 'axios';
import { getCurrentUser } from './auth';

const baseUrl = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
const API_BASE = new URL('/api', baseUrl).toString();

function getToken() {
  const user = getCurrentUser();
  if (!user || !user.token) {
    throw new Error('User not authenticated. Please log in.');
  }
  return user.token;
}

export const evaluationService = {
  async getEvaluationSchemes(courseId) {
    try {
      const res = await axios.get(`${API_BASE}/evaluation/schemes/${courseId}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });
      return res.data.schemes || [];
    } catch (error) {
      console.error('Get evaluation schemes error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please log in again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to get evaluation schemes');
    }
  },

  async uploadEvaluationScheme({ courseId, schemeName, schemeDescription, markSchemeFile }) {
    const formData = new FormData();
    formData.append('course_id', courseId);
    formData.append('scheme_name', schemeName);
    formData.append('scheme_description', schemeDescription);
    formData.append('mark_scheme', markSchemeFile);
    
    try {
      const res = await axios.post(`${API_BASE}/evaluation/upload-scheme`, formData, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      return res.data;
    } catch (error) {
      console.error('Upload evaluation scheme error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please log in again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to upload evaluation scheme');
    }
  },

  async uploadEvaluationFiles({ userId, courseId, markSchemeFile, answerSheetFiles, schemeId = null }) {
    const formData = new FormData();
    formData.append('user_id', userId);
    formData.append('courseId', courseId);
    if (schemeId) {
      formData.append('scheme_id', schemeId);
    } else if (markSchemeFile) {
      formData.append('mark_scheme', markSchemeFile);
    }
    if (Array.isArray(answerSheetFiles)) {
      answerSheetFiles.forEach(f => formData.append('answer_sheets', f));
    } else if (answerSheetFiles) {
      formData.append('answer_sheets', answerSheetFiles);
    }
    
    try {
      const res = await axios.post(`${API_BASE}/evaluation/upload-files`, formData, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      return res.data; // { evaluation_id: "uuid" }
    } catch (error) {
      console.error('Upload error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please log in again.');
      }
      throw new Error(error.response?.data?.detail || 'Upload failed');
    }
  },

  async evaluateFiles(evaluationId) {
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        throw new Error('User not authenticated');
      }

      const res = await axios.get(`${API_BASE}/evaluation/evaluate-files`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        params: {
          evaluation_id: evaluationId,
          user_id: user.id
        }
      });
      return res.data; // { evaluation_id: "uuid", evaluation_result: {...} }
    } catch (error) {
      console.error('Evaluation error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please log in again.');
      }
      throw new Error(error.response?.data?.detail || 'Evaluation failed');
    }
  }
}; 