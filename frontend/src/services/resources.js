// Resources service for file uploads and management
const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000/api';

// Helper to get the Firebase token from localStorage
function getToken() {
  return localStorage.getItem('authToken');
}

// Helper to handle API responses
async function handleResponse(response) {
  console.log('handleResponse called with status:', response.status);
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    console.error('API error:', errorData);
    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
  }
  
  const data = await response.json();
  console.log('API response data:', data);
  return data;
}

// Helper to generate a unique filename
function makeUniqueFile(file) {
  const ext = file.name.includes('.') ? file.name.substring(file.name.lastIndexOf('.')) : '';
  const base = file.name.replace(ext, '').replace(/[^a-zA-Z0-9_-]/g, '');
  const unique = `${Date.now()}_${Math.random().toString(36).substr(2, 6)}_${base}${ext}`;
  return new File([file], unique, { type: file.type });
}

// Upload files to course (course-level resources)
export async function uploadCourseResources(courseId, files) {
  console.log('uploadCourseResources called with:', { courseId, files: files.map(f => f.name) });
  const formData = new FormData();
  files.forEach(file => {
    const uniqueFile = makeUniqueFile(file);
    formData.append('files', uniqueFile);
  });
  const token = getToken();
  console.log('Using token:', token ? 'Token exists' : 'No token');
  console.log('API URL:', `${API_BASE}/courses/${courseId}/resources`);
  const res = await fetch(`${API_BASE}/courses/${courseId}/resources`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });
  console.log('Response status:', res.status);
  return handleResponse(res);
}

// Upload files to asset thread (asset-level resources)
export async function uploadAssetResources(courseId, threadId, files) {
  const formData = new FormData();
  files.forEach(file => {
    const uniqueFile = makeUniqueFile(file);
    formData.append('files', uniqueFile);
  });
  const res = await fetch(`${API_BASE}/courses/${courseId}/resources?thread_id=${threadId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getToken()}`
    },
    body: formData
  });
  return handleResponse(res);
}

// Get asset-level resources
export async function getAssetResources(courseId, threadId) {
  const res = await fetch(`${API_BASE}/courses/${courseId}/resources?thread_id=${threadId}`, {
    headers: {
      'Authorization': `Bearer ${getToken()}`
    }
  });
  return handleResponse(res);
}

// Get brainstorm-specific resources
export async function getBrainstormResources(courseId, threadId) {
  const res = await fetch(`${API_BASE}/courses/${courseId}/brainstorm/${threadId}/resources`, {
    headers: {
      'Authorization': `Bearer ${getToken()}`
    }
  });
  return handleResponse(res);
}

// Delete a resource
export async function deleteResource(courseId, fileId) {
  const res = await fetch(`${API_BASE}/courses/${courseId}/files/${fileId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${getToken()}`
    }
  });
  return handleResponse(res);
}

// Add checked-in files to assistant/thread
export async function addCheckedInFilesToThread(courseId, threadId) {
  const res = await fetch(`${API_BASE}/courses/${courseId}/assistant/resources?thread_id=${threadId}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getToken()}`
    }
  });
  return handleResponse(res);
}

// Fix incompatible files
export async function fixIncompatibleFiles(courseId) {
  const res = await fetch(`${API_BASE}/courses/${courseId}/assistant/fix-files`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getToken()}`
    }
  });
  return handleResponse(res);
}

// Create URL resource
export async function createUrlResource(courseId, title, url, threadId = null) {
  const params = threadId ? `?thread_id=${threadId}` : '';
  const res = await fetch(`${API_BASE}/courses/${courseId}/resources/url${params}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`
    },
    body: JSON.stringify({ title, url })
  });
  return handleResponse(res);
}

// Upload files with progress tracking
export async function uploadFilesWithProgress(courseId, files, threadId = null, onProgress = null) {
  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file);
  });

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

export async function updateResourceStatus(courseId, fileId, status) {
  const formData = new FormData();
  formData.append('status', status);
  const res = await fetch(`${API_BASE}/courses/${courseId}/resources/${fileId}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${getToken()}`
    },
    body: formData
  });
  if (!res.ok) throw new Error('Failed to update resource status');
  return res.json();
} 