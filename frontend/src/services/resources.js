import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';

function getToken() {
  const token = localStorage.getItem('token');
  console.log('Getting token:', token ? 'Token exists' : 'No token found');
  return token;
}

function handleAxiosError(error) {
  if (error.response && error.response.data && error.response.data.detail) {
    throw new Error(error.response.data.detail);
  }
  throw new Error(error.message || 'Unknown error');
}

export async function uploadCourseResources(courseId, files) {
  console.log('uploadCourseResources called with:', { courseId, filesCount: files.length });
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  try {
    const res = await axios.post(`${API_BASE}/courses/${courseId}/resources`, formData, {
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    console.log('Upload response:', res.data);
    return res.data;
  } catch (error) {
    console.error('Upload error:', error);
    handleAxiosError(error);
  }
}

export async function uploadAssetResources(courseId, threadId, files) {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  try {
    const res = await axios.post(`${API_BASE}/courses/${courseId}/resources?thread_id=${threadId}`, formData, {
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function getCourseResources(courseId) {
  try {
    const res = await axios.get(`${API_BASE}/courses/${courseId}/resources`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function getAssetResources(courseId, threadId) {
  try {
    const res = await axios.get(`${API_BASE}/courses/${courseId}/resources?thread_id=${threadId}`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function getBrainstormResources(courseId, threadId) {
  try {
    const res = await axios.get(`${API_BASE}/courses/${courseId}/brainstorm/${threadId}/resources`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function checkoutResource(courseId, fileId) {
  try {
    const userId = localStorage.getItem("userId");
    const res = await axios.put(
      `${API_BASE}/courses/${courseId}/resources/${fileId}/checkout`,
      { userId },
      {
        headers: { Authorization: `Bearer ${getToken()}` }
      }
    );
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function checkinResource(courseId, fileId) {
  try {
    const res = await axios.put(`${API_BASE}/courses/${courseId}/resources/${fileId}/checkin`, {}, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function deleteResource(courseId, fileId) {
  try {
    const res = await axios.delete(`${API_BASE}/courses/${courseId}/resources/${fileId}`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function addCheckedInFilesToThread(courseId, threadId) {
  try {
    const res = await axios.post(`${API_BASE}/courses/${courseId}/assistant/resources?thread_id=${threadId}`, {}, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function fixIncompatibleFiles(courseId) {
  try {
    const res = await axios.post(`${API_BASE}/courses/${courseId}/assistant/fix-files`, {}, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function createUrlResource(courseId, title, url, threadId = null) {
  try {
    const params = threadId ? `?thread_id=${threadId}` : '';
    const res = await axios.post(`${API_BASE}/courses/${courseId}/resources/url${params}`, { title, url }, {
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

export async function addAllFilesToAssistant(courseId, threadId) {
  try {
    const res = await axios.post(
      `${API_BASE}/courses/${courseId}/assistant/resources?thread_id=${threadId}`,
      {},
      {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      }
    );
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export function uploadFilesWithProgress(courseId, files, threadId = null, onProgress = null) {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  const xhr = new XMLHttpRequest();
  return new Promise((resolve, reject) => {
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable && onProgress) {
        const percentComplete = (event.loaded / event.total) * 100;
        onProgress(percentComplete);
      }
    });
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText);
          resolve(response);
        } catch (error) {
          reject(new Error('Invalid JSON response'));
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`));
      }
    });
    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed'));
    });
    const url = threadId 
      ? `${API_BASE}/courses/${courseId}/resources?thread_id=${threadId}`
      : `${API_BASE}/courses/${courseId}/resources`;
    xhr.open('POST', url);
    xhr.setRequestHeader('Authorization', `Bearer ${getToken()}`);
    xhr.send(formData);
  });
} 