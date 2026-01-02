import axios from 'axios';
import { API_BASE } from '../utils/axiosConfig';

/**
 * SuperAdmin API Service
 * Handles organization and superadmin management
 */

// Get auth headers
const getAuthHeaders = () => {
    const token = localStorage.getItem('token');
    return {
        headers: {
            Authorization: `Bearer ${token}`,
        },
    };
};

// ============== ORGANIZATION OPERATIONS ==============

export async function createOrganization(orgName, adminEmail, adminPassword = null) {
    const response = await axios.post(
        `${API_BASE}/superadmin/organizations`,
        {
            org_name: orgName,
            admin_email: adminEmail,
            admin_password: adminPassword,
        },
        getAuthHeaders()
    );
    return response.data;
}

export async function getOrganizations() {
    const response = await axios.get(
        `${API_BASE}/superadmin/organizations`,
        getAuthHeaders()
    );
    return response.data;
}

export async function getOrganization(orgId) {
    const response = await axios.get(
        `${API_BASE}/superadmin/organizations/${orgId}`,
        getAuthHeaders()
    );
    return response.data;
}

export async function deleteOrganization(orgId) {
    const response = await axios.delete(
        `${API_BASE}/superadmin/organizations/${orgId}`,
        getAuthHeaders()
    );
    return response.data;
}

// ============== SUPERADMIN USER OPERATIONS ==============

export async function createSuperAdmin(email, password, displayName = null) {
    const response = await axios.post(
        `${API_BASE}/superadmin/create-superadmin`,
        {
            email,
            password,
            display_name: displayName,
        },
        getAuthHeaders()
    );
    return response.data;
}

export async function getSuperAdmins() {
    const response = await axios.get(
        `${API_BASE}/superadmin/superadmins`,
        getAuthHeaders()
    );
    return response.data;
}

// ============== VERIFICATION ==============

export async function verifySuperAdminAccess() {
    const response = await axios.get(
        `${API_BASE}/superadmin/verify`,
        getAuthHeaders()
    );
    return response.data;
}

// ============== PAYMENT CONFIGURATION ==============

export async function getPaymentConfig() {
    const response = await axios.get(
        `${API_BASE}/superadmin/payment-config`,
        getAuthHeaders()
    );
    return response.data;
}

export async function setPaymentConfig(pricePerUserPaise, currency = 'INR') {
    const response = await axios.post(
        `${API_BASE}/superadmin/payment-config`,
        {
            price_per_user_paise: pricePerUserPaise,
            currency: currency,
        },
        getAuthHeaders()
    );
    return response.data;
}

// ============== SETTINGS MANAGEMENT ==============

export async function getAllSettings() {
    const response = await axios.get(
        `${API_BASE}/superadmin/settings`,
        getAuthHeaders()
    );
    return response.data;
}

export async function addSettingLabel(category, label) {
    const response = await axios.post(
        `${API_BASE}/superadmin/settings/${category}/labels`,
        { label },
        getAuthHeaders()
    );
    return response.data;
}

export async function removeSettingLabel(category, label) {
    const response = await axios.delete(
        `${API_BASE}/superadmin/settings/${category}/labels/${encodeURIComponent(label)}`,
        getAuthHeaders()
    );
    return response.data;
}
