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

export const assetService = {
    getFirstMessage: async (courseId, assetName, inputVariables) => {
        try {
          const res = await axios.post(`${API_BASE}/courses/${courseId}/assets/${assetName}`, { input_variables: inputVariables }, {
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${getToken()}`
            }
          });
          return res.data;
        } catch (error) {
          handleAxiosError(error);
        }
      }
}; 