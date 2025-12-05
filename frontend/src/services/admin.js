import axiosInstance from '../utils/axiosConfig';

/**
 * Upload a document to admin files
 */
export async function uploadAdminDocument(documentTitle, file) {
  const formData = new FormData();
  formData.append('document_title', documentTitle);
  formData.append('file', file);

  const res = await axiosInstance.post('/admin/documents', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return res.data;
}

/**
 * Get all admin documents
 */
export async function getAdminDocuments() {
  const res = await axiosInstance.get('/admin/documents');
  return res.data;
}

/**
 * Download an admin document
 */
export async function downloadAdminDocument(fileId, filename) {
  const res = await axiosInstance.get(`/admin/documents/${fileId}/download`, {
    responseType: 'blob',
  });
  
  // Create download link
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Delete an admin document
 */
export async function deleteAdminDocument(fileId) {
  const res = await axiosInstance.delete(`/admin/documents/${fileId}`);
  return res.data;
}

/**
 * Get all setting labels
 */
export async function getAllSettings() {
  const res = await axiosInstance.get('/admin/settings');
  return res.data;
}

/**
 * Add a label to a setting category
 */
export async function addSettingLabel(category, label) {
  const res = await axiosInstance.post(`/admin/settings/${category}/labels`, { label });
  return res.data;
}

/**
 * Remove a label from a setting category
 */
export async function removeSettingLabel(category, label) {
  const res = await axiosInstance.delete(`/admin/settings/${category}/labels/${encodeURIComponent(label)}`);
  return res.data;
}

/**
 * Get all users
 */
export async function getAllUsers() {
  const res = await axiosInstance.get('/admin/users');
  return res.data;
}

/**
 * Update user role
 */
export async function updateUserRole(userId, role) {
  const res = await axiosInstance.put(`/admin/users/${userId}/role`, { role });
  return res.data;
}

/**
 * Create a new user
 */
export async function createUser(email, displayName, role) {
  const res = await axiosInstance.post('/admin/users', {
    email,
    display_name: displayName,
    role
  });
  return res.data;
}

/**
 * Delete a user
 */
export async function deleteUser(userId) {
  const res = await axiosInstance.delete(`/admin/users/${userId}`);
  return res.data;
}

