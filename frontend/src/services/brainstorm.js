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

export async function createBrainstormThread(courseId) {
  try {
    const res = await axios.post(
      `${API_BASE}/courses/${courseId}/brainstorm/threads`,
      undefined, // No body
      {
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      }
    );
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function getBrainstormMessages(courseId, threadId) {
  try {
    const res = await axios.get(`${API_BASE}/courses/${courseId}/brainstorm/${threadId}/messages`, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
    return res.data;
  } catch (error) {
    handleAxiosError(error);
  }
}

export async function sendBrainstormMessageStream(courseId, threadId, message, onToken) {
  const res = await fetch(`${API_BASE}/courses/${courseId}/brainstorm/${threadId}/messages/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`
    },
    body: JSON.stringify({ message })
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `HTTP error! status: ${res.status}`);
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
} 