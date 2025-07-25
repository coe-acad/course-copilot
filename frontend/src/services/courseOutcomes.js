import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

function getToken() {
  return localStorage.getItem('token');
}

function handleAxiosError(error) {
  if (error.response && error.response.data && error.response.data.detail) {
    throw new Error(error.response.data.detail);
  }
  throw new Error(error.message || 'Unknown error');
}

export const courseOutcomesService = {
  createThread: async (courseId, assetName, inputVariables = {}) => {
    try {
      const res = await axios.post(`${API_BASE}/courses/${courseId}/assets/${assetName}`,
        { input_variables: inputVariables }, // Always send this shape
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
          }
        }
      );
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },
  startSession: async (courseId, courseName, clarifyingQuestions, fileNames = []) => {
    try {
      const res = await axios.post(`${API_BASE}/courses/${courseId}/course-outcomes/start`, {
        course_name: courseName,
        ask_clarifying_questions: clarifyingQuestions,
        file_names: fileNames
      }, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getToken()}`
        }
      });
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },
  sendMessage: async (courseId, threadId, message) => {
    try {
      const res = await axios.post(`${API_BASE}/courses/${courseId}/course-outcomes/${threadId}/message`, { message }, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getToken()}`
        }
      });
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },
  sendMessageStream: async (courseId, threadId, message, onToken) => {
    const res = await fetch(`${API_BASE}/courses/${courseId}/course-outcomes/${threadId}/message/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`
      },
      body: JSON.stringify({ message })
    });
    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.detail || 'Failed to send message');
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'token') {
              onToken(data.content, data.is_complete);
              if (data.is_complete) {
                return;
              }
            }
          } catch (e) {
            console.warn('Invalid JSON in stream:', line.slice(6));
          }
        }
      }
    }
  },
  getMessages: async (courseId, threadId) => {
    try {
      const res = await axios.get(`${API_BASE}/courses/${courseId}/course-outcomes/${threadId}/messages`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },
  getThreads: async (courseId) => {
    try {
      const res = await axios.get(`${API_BASE}/courses/${courseId}/course-outcomes/threads`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },
}; 