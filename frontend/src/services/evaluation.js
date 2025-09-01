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
        throw new Error('Authentication failed. Please try agian.');
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
        throw new Error('Authentication failed. Please try agian.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to upload answer sheets');
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
        throw new Error('Authentication failed. Please try agian.');
      }
      throw new Error(error.response?.data?.detail || 'Evaluation failed');
    }
  },

  async updateStudentResult({ evaluationId, studentIndex, questionScores, feedback }) {
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        throw new Error('User not authenticated');
      }

      const res = await axios.put(`${API_BASE}/evaluation/update-student-result`, {
        evaluation_id: evaluationId,
        student_index: studentIndex,
        question_scores: questionScores,
        feedback: feedback
      }, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        }
      });
      
      return res.data; // { message: "Student result updated successfully", total_score: 15, status: "modified" }
    } catch (error) {
      console.error('Update student result error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try agian.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to update student result');
    }
  },

  async updateStudentStatus({ evaluationId, studentIndex, status }) {
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        throw new Error('User not authenticated');
      }

      const res = await axios.put(`${API_BASE}/evaluation/update-student-status`, {
        evaluation_id: evaluationId,
        student_index: studentIndex,
        status: status
      }, {
        headers: { 
          'Authorization': `Bearer ${getToken()}`,
          'Content-Type': 'application/json'
        }
      });
      
      return res.data; // { message: "Student status updated successfully", status: "opened" }
    } catch (error) {
      console.error('Update student status error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try agian.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to update student status');
    }
  },

  async editQuestionResult({ evaluationId, fileId, questionNumber, score, feedback }) {
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        throw new Error('User not authenticated');
      }

      console.log('Sending data to backend:', {
        evaluation_id: evaluationId,
        file_id: fileId,
        question_number: questionNumber,
        score: score,
        feedback: feedback
      });
      
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
      
      return res.data; // { message: "Results updated successfully" }
    } catch (error) {
      console.error('Edit question result error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try agian.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to edit question result');
    }
  },

  async getStudentEvaluationDetails({ evaluationId, studentIndex }) {
    try {
      const user = getCurrentUser();
      if (!user?.id) {
        throw new Error('User not authenticated');
      }

      const res = await axios.get(`${API_BASE}/evaluation/student-details`, {
        headers: { 'Authorization': `Bearer ${getToken()}` },
        params: {
          evaluation_id: evaluationId,
          student_index: studentIndex,
          user_id: user.id
        }
      });
      
      return res.data; // Student evaluation details
    } catch (error) {
      console.error('Get student details error:', error);
      if (error.response?.status === 401) {
        throw new Error('Authentication failed. Please try agian.');
      }
      throw new Error(error.response?.data?.detail || 'Failed to get student details');
    }
  }
}; 