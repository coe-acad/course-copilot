import axios from 'axios';
import { getCurrentUser } from './auth';

const baseUrl = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
const API_BASE = new URL('/api', baseUrl).toString();

// Track ongoing evaluation requests to prevent duplicates
const ongoingEvaluations = new Set();
// Track completed evaluations to prevent re-evaluation
const completedEvaluations = new Set();

function getToken() {
  const user = getCurrentUser();
  if (!user || !user.token) {
    throw new Error('User not authenticated. Please log in.');
  }
  return user.token;
}

export const evaluationService = {
  // Clear completed evaluations tracking (useful when starting fresh)
  clearCompletedEvaluations() {
    completedEvaluations.clear();
    ongoingEvaluations.clear();
  },

  async uploadMarkScheme({ courseId, markSchemeFile }) {
    const formData = new FormData();
    formData.append('course_id', courseId);
    formData.append('mark_scheme', markSchemeFile);
    
    try {
      const res = await axios.post(`${API_BASE}/evaluation/upload-mark-scheme`, formData, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      return res.data; // { evaluation_id: "uuid", mark_scheme_file_id: "uuid" }
    } catch (error) {
      console.error('Upload mark scheme error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to upload mark scheme');
    }
  },

  async uploadAnswerSheets({ evaluationId, answerSheetFiles }) {
    const formData = new FormData();
    formData.append('evaluation_id', evaluationId);
    if (Array.isArray(answerSheetFiles)) {
      answerSheetFiles.forEach(f => formData.append('answer_sheets', f));
    } else if (answerSheetFiles) {
      formData.append('answer_sheets', answerSheetFiles);
    }
    
    try {
      const res = await axios.post(`${API_BASE}/evaluation/upload-answer-sheets`, formData, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      return res.data; // { evaluation_id: "uuid", answer_sheet_file_ids: ["uuid1", "uuid2"] }
    } catch (error) {
      console.error('Upload answer sheets error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to upload answer sheets');
    }
  },

  async evaluateFiles(evaluationId, { signal } = {}) {
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        throw new Error('User not authenticated');
      }

      console.log('🚀 Calling evaluation endpoint with:', {
        evaluation_id: evaluationId,
        user_id: user.id
      });

      // Simple direct call to evaluation endpoint
      const res = await axios.get(`${API_BASE}/evaluation/evaluate-files`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        params: {
          evaluation_id: evaluationId,
          user_id: user.id
        },
        timeout: 300000, // 5 minutes timeout for long evaluation
        signal
      });
      
      console.log('✅ Evaluation response:', res.data);
      return res.data; // { evaluation_id: "uuid", evaluation_result: {...} }
    } catch (error) {
      console.error('Evaluation error details:', {
        message: error.message,
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        evaluationId: evaluationId,
        code: error.code
      });
      
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      
      // Do not fall back to polling; surface timeout to the caller
      if (error.response?.status === 504 || error.code === 'ECONNABORTED') {
        ongoingEvaluations.delete(evaluationId);
        throw new Error('Evaluation timed out. Please try again or check back later.');
      }
      
      if (error.response?.status >= 500) {
        const errorDetail = error.response?.data?.detail || 'Server error during evaluation';
        throw new Error(`Server error: ${errorDetail}. The backend may still be processing. Please try again in a few minutes.`);
      }
      
      if (error.response?.status === 404) {
        throw new Error('Evaluation session not found. Please restart the evaluation process.');
      }
      
      // Always clean up tracking in catch block
      ongoingEvaluations.delete(evaluationId);
      throw new Error(error.response?.data?.detail || `Evaluation failed: ${error.message}`);
        }
  },

  async checkCompletedEvaluation(evaluationId, { signal } = {}) {
    try {
      const res = await axios.get(`${API_BASE}/evaluation/status/${evaluationId}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        timeout: 10000,
        signal
      });
      
      if (res.data.status === 'completed') {
        completedEvaluations.add(evaluationId);
        return { status: 'completed', evaluation_result: res.data.evaluation_result };
      }

      return { status: 'processing' };
    } catch (error) {
      console.error('Fallback evaluation check error:', error);
      throw error;
    }
  },

  async editQuestionResult({ evaluationId, fileId, questionNumber, score, feedback }) {
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        throw new Error('User not authenticated');
      }
      
      const res = await axios.put(`${API_BASE}/evaluation/edit-results`, {
        evaluation_id: evaluationId,
        file_id: fileId,
        question_number: questionNumber,
        score: score,
        feedback: feedback
      }, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        }
      });
      
      return res.data; // { message: "Results updated" }
    } catch (error) {
      console.error('Edit question result error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to edit question result');
    }
  },

  async saveEvaluation(evaluationId, assetName, fileName) {
    try {
      const formData = new FormData();
      formData.append('asset_name', assetName);
      formData.append('file_name', fileName);
      const res = await axios.post(`${API_BASE}/evaluation/save/${evaluationId}`, formData, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      
      return res.data;
    } catch (error) {
      console.error('Save evaluation error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to save evaluation');
    }
  }
}; 