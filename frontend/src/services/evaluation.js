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
  async uploadEvaluationFiles({ userId, courseId, markSchemeFile, answerSheetFiles }) {
    const formData = new FormData();
    formData.append('user_id', userId);
    formData.append('course_id', courseId);
    formData.append('mark_scheme', markSchemeFile);
    if (Array.isArray(answerSheetFiles)) {
      answerSheetFiles.forEach(f => formData.append('answer_sheets', f));
    } else if (answerSheetFiles) {
      formData.append('answer_sheet', answerSheetFiles);
    }
    const res = await axios.post(`${API_BASE}/evaluation/upload-files`, formData, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data; // { mark_scheme: "id", answer_sheet: ["id1", "id2", ...] }
  }
}; 