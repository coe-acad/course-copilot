import axiosInstance from '../utils/axiosConfig';

/**
 * Fetch all curriculum feature configurations
 */
export async function getCurriculumConfigurations() {
  const res = await axiosInstance.get('/configurations/curriculum');
  return res.data;
}

/**
 * Fetch all assessment feature configurations
 */
export async function getAssessmentConfigurations() {
  const res = await axiosInstance.get('/configurations/assessment');
  return res.data;
}

/**
 * Fetch all settings configurations
 */
export async function getAllSettingsConfigurations() {
  const res = await axiosInstance.get('/configurations/settings');
  return res.data;
}

/**
 * Fetch a specific setting configuration by category
 */
export async function getSettingByCategory(category) {
  const res = await axiosInstance.get(`/configurations/settings/${category}`);
  return res.data;
}

/**
 * Create a new configuration (admin only)
 */
export async function createConfiguration(configData) {
  const res = await axiosInstance.post('/configurations', configData);
  return res.data;
}

/**
 * Update an existing configuration (admin only)
 */
export async function updateConfiguration(configId, configData) {
  const res = await axiosInstance.put(`/configurations/${configId}`, configData);
  return res.data;
}

/**
 * Delete a configuration (admin only)
 */
export async function deleteConfiguration(configId) {
  const res = await axiosInstance.delete(`/configurations/${configId}`);
  return res.data;
}

