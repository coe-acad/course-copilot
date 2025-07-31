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
  // Get all assets for a course
  getAssets: async (courseId) => {
    try {
      const res = await axios.get(`${API_BASE}/courses/${courseId}/assets`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      });
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Create initial asset chat with selected files
  createAssetChat: async (courseId, assetTypeName, fileNames) => {
    try {
      const res = await axios.post(`${API_BASE}/courses/${courseId}/asset_chat/${assetTypeName}`, 
        { file_names: fileNames }, 
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

  // Continue asset chat conversation
  continueAssetChat: async (courseId, assetName, threadId, userPrompt) => {
    try {
      const res = await axios.put(`${API_BASE}/courses/${courseId}/asset_chat/${assetName}?thread_id=${threadId}`, 
        { user_prompt: userPrompt }, 
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

  // Save asset to database
  saveAsset: async (courseId, assetName, assetType, content) => {
    try {
      const res = await axios.post(`${API_BASE}/courses/${courseId}/assets`, 
        { content: content }, 
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
          },
          params: {
            asset_name: assetName,
            asset_type: assetType
          }
        }
      );
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  }
}; 