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
  async uploadMarkScheme({ courseId, markSchemeFile }) {
    const formData = new FormData();
    formData.append('course_id', courseId);
    formData.append('mark_scheme', markSchemeFile);
    
    const res = await axios.post(`${API_BASE}/evaluation/upload-mark-scheme`, formData, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data; // { evaluation_id: "id", mark_scheme_file_id: "id" }
  },

  async uploadAnswerSheets({ evaluationId, answerSheetFiles }) {
    const formData = new FormData();
    formData.append('evaluation_id', evaluationId);
    
    if (Array.isArray(answerSheetFiles)) {
      answerSheetFiles.forEach(f => formData.append('answer_sheets', f));
    }
    
    const res = await axios.post(`${API_BASE}/evaluation/upload-answer-sheets`, formData, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data; // { evaluation_id: "id", answer_sheet_file_ids: ["id1", "id2", ...] }
  },

  async evaluateFiles({ evaluationId }) {
    const res = await axios.get(`${API_BASE}/evaluation/evaluate-files`, {
      params: { evaluation_id: evaluationId },
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  }
}; 