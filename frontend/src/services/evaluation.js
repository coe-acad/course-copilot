import axios from 'axios';
import { getCurrentUser } from './auth';

const baseUrl = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
const API_BASE = new URL('/api', baseUrl).toString();

// Track ongoing evaluation requests to prevent duplicates
const ongoingEvaluations = new Set();
// Track last evaluation request timestamps to prevent rapid duplicates
const lastEvaluationTime = new Map();
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
    const now = Date.now();
    const lastRequestTime = lastEvaluationTime.get(evaluationId) || 0;
    
    // Check if this evaluation is already completed
    if (completedEvaluations.has(evaluationId)) {
      throw new Error('This evaluation has already been completed. Please refresh the page.');
    }
    
    // Prevent duplicate requests for the same evaluation
    if (ongoingEvaluations.has(evaluationId)) {
      throw new Error('Evaluation already in progress for this ID');
    }
    
    // NUCLEAR PROTECTION: Prevent rapid successive requests (within 3 seconds)
    if (now - lastRequestTime < 3000) {
      throw new Error('Duplicate request blocked - please wait');
    }
    
    ongoingEvaluations.add(evaluationId);
    lastEvaluationTime.set(evaluationId, now);
    
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        ongoingEvaluations.delete(evaluationId);
        throw new Error('User not authenticated');
      }


      // Idempotent trigger: backend returns completed if already done, or processing once
      const res = await axios.get(`${API_BASE}/evaluation/evaluate-files`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        params: {
          evaluation_id: evaluationId,
          user_id: user.id
        },
        timeout: 30000,
        signal
      });
      
      
      // If backend is processing in background, poll for completion
      if (res.data.evaluation_result?.status === 'processing') {
        ongoingEvaluations.delete(evaluationId);
        return await this.waitForCompletion(evaluationId);
      }
      
      // Mark as completed to prevent re-evaluation
      if (res.data.evaluation_result && res.data.evaluation_result.status !== 'processing') {
        completedEvaluations.add(evaluationId);
      }
      
      ongoingEvaluations.delete(evaluationId); // Clean up tracking
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
      
      // On timeout, switch to polling mode via status endpoint
      if (error.response?.status === 504 || error.code === 'ECONNABORTED') {
        ongoingEvaluations.delete(evaluationId);
        
        // Start polling immediately when timeout occurs
        try {
          return await this.waitForCompletion(evaluationId);
        } catch (pollingError) {
          throw new Error('Evaluation is taking longer than expected. The process may still be running. Please check back later or contact support if the issue persists.');
        }
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

  async waitForCompletion(evaluationId, { signal } = {}) {
    // Poll status every 5 seconds for up to 20 minutes
    for (let i = 0; i < 240; i++) {
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      try {
        const res = await axios.get(`${API_BASE}/evaluation/status/${evaluationId}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` },
          timeout: 10000,
          signal
        });
        
        
        if (res.data.status === 'completed') {
          // Mark as completed to prevent re-evaluation
          completedEvaluations.add(evaluationId);
          return { evaluation_id: evaluationId, evaluation_result: res.data.evaluation_result };
        }
        
        // Log progress for debugging
        if (i % 6 === 0) { // Every 30 seconds
        }
      } catch (error) {
        console.warn(`Polling attempt ${i + 1} failed:`, error.message);
        // Continue polling even if individual requests fail
        if (error.response?.status === 401) {
          throw new Error('Authentication failed during polling');
        }
      }
    }
    
    throw new Error('Evaluation timed out after 20 minutes. Please check the evaluation status manually.');
  },

  async checkEvaluationStatus(evaluationId, { signal } = {}) {
    try {
      const res = await axios.get(`${API_BASE}/evaluation/status/${evaluationId}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        timeout: 10000,
        signal
      });
      
      
      // Mark as completed if we get a completed status
      if (res.data.status === 'completed') {
        completedEvaluations.add(evaluationId);
      }
      
      return res.data; // { status: "completed" | "processing", evaluation_result?: {...} }
    } catch (error) {
      console.error('Status check error:', error);
      
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try again.');
      }
      
      if (error.response?.status === 404) {
        // 404 might mean the evaluation was not created properly or was deleted
        // Let's provide more context
        console.warn(`Evaluation ${evaluationId} not found (404). This might be a timing issue or the evaluation was not created properly.`);
        throw new Error('Evaluation not found. Please try restarting the evaluation process.');
      }
      
      if (error.response?.status >= 500) {
        throw new Error('Server error while checking evaluation status. Please try again.');
      }
      
      // For other errors, provide a generic message but don't fail completely
      console.warn('Status check failed, but continuing to retry:', error.message);
      throw new Error(error.response?.data?.detail || 'Failed to check evaluation status');
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