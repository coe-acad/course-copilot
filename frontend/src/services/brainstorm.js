// Brainstorm service for API calls to backend
const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000/api';

// Helper to get the Firebase token from localStorage
function getAuthToken() {
  return localStorage.getItem('authToken');
}

// Helper to handle API responses
async function handleResponse(response) {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

// Create a new brainstorm thread for a course
export async function createBrainstormThread(courseId) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('No authentication token found');
  }

  const res = await fetch(`${API_BASE}/courses/${courseId}/brainstorm/threads`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    }
  });
  return handleResponse(res);
}

// Get brainstorm messages for a specific thread
export async function getBrainstormMessages(courseId, threadId) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('No authentication token found');
  }

  const res = await fetch(`${API_BASE}/courses/${courseId}/brainstorm/${threadId}/messages`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return handleResponse(res);
}

// Send a message to a brainstorm thread (non-streaming)
export async function sendBrainstormMessage(courseId, threadId, message) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('No authentication token found');
  }

  const res = await fetch(`${API_BASE}/courses/${courseId}/brainstorm/${threadId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ message })
  });
  return handleResponse(res);
}

// Send a message to a brainstorm thread with streaming
export async function sendBrainstormMessageStream(courseId, threadId, message, onToken, checkedInFiles = [], checkedOutFiles = []) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('No authentication token found');
  }

  const res = await fetch(`${API_BASE}/courses/${courseId}/brainstorm/${threadId}/messages/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ message, checkedInFiles, checkedOutFiles })
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  // Helper function to add delay
  const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

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
            
            // Add a small delay between tokens to make streaming visible
            // Adjust this value (50ms) to control the speed
            await delay(50);
            
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
} 

// --- General Chat Thread Functions (for Studio.js) ---

// Create a new general chat thread for a course
export async function createChatThread(courseId) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('No authentication token found');
  }
  const res = await fetch(`${API_BASE}/courses/${courseId}/threads`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    }
  });
  return handleResponse(res);
}

// Get chat messages for a specific thread (non-brainstorm)
export async function getChatMessages(courseId, threadId) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('No authentication token found');
  }
  const res = await fetch(`${API_BASE}/courses/${courseId}/threads/${threadId}/messages`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return handleResponse(res);
}

// Send a message to a general chat thread with streaming (non-brainstorm)
export async function sendChatMessageStream(courseId, threadId, message, onToken, checkedInFiles = [], checkedOutFiles = []) {
  const token = getAuthToken();
  if (!token) {
    throw new Error('No authentication token found');
  }
  const res = await fetch(`${API_BASE}/courses/${courseId}/threads/${threadId}/messages/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ message, checkedInFiles, checkedOutFiles })
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
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
            await delay(50);
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
} 