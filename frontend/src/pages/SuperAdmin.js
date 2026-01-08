import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { FiHome, FiUsers, FiLogOut, FiPlus, FiTrash2, FiEye, FiEyeOff, FiDollarSign, FiTag } from "react-icons/fi";
import {
    verifySuperAdminAccess,
    getOrganizations,
    createOrganization,
    deleteOrganization,
    getPaymentConfig,
    setPaymentConfig,
    getAllSettings,
    addSettingLabel,
    removeSettingLabel,
} from "../services/superadmin";

export default function SuperAdmin() {
    const [checking, setChecking] = useState(true);
    const [accessDenied, setAccessDenied] = useState(false);
    const [organizations, setOrganizations] = useState([]);
    const [loading, setLoading] = useState(false);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [activeTab, setActiveTab] = useState("organizations");
    const navigate = useNavigate();

    // Form state
    const [orgName, setOrgName] = useState("");
    const [adminEmail, setAdminEmail] = useState("");
    const [adminPassword, setAdminPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState("");
    const [createdOrg, setCreatedOrg] = useState(null);

    // Payment config state
    const [paymentConfig, setPaymentConfigState] = useState(null);
    const [priceInput, setPriceInput] = useState("");
    const [savingPrice, setSavingPrice] = useState(false);

    // Settings state
    const [settings, setSettings] = useState([]);
    const [settingsLoading, setSettingsLoading] = useState(false);
    const [newLabels, setNewLabels] = useState({});

    // Helper function to format category names
    const formatCategoryName = (category) => {
        return category
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    };

    // Verify superadmin access on mount
    useEffect(() => {
        checkAccess();
    }, []);

    const checkAccess = async () => {
        try {
            setChecking(true);
            await verifySuperAdminAccess();
            setAccessDenied(false);
            loadOrganizations();
        } catch (err) {
            if (err.response?.status === 403 || err.response?.status === 401) {
                setAccessDenied(true);
            }
        } finally {
            setChecking(false);
        }
    };

    const loadOrganizations = async () => {
        try {
            setLoading(true);
            const data = await getOrganizations();
            setOrganizations(data.organizations || []);
        } catch (err) {
            console.error("Error loading organizations:", err);
        } finally {
            setLoading(false);
        }
    };

    const loadPaymentConfig = async () => {
        try {
            const config = await getPaymentConfig();
            setPaymentConfigState(config);
            if (config.configured) {
                setPriceInput((config.price_per_user_paise / 100).toString());
            }
        } catch (err) {
            console.error("Error loading payment config:", err);
        }
    };

    const handleSavePrice = async () => {
        const priceValue = parseFloat(priceInput);
        if (isNaN(priceValue) || priceValue < 0) {
            alert("Please enter a valid price");
            return;
        }

        try {
            setSavingPrice(true);
            const priceInPaise = Math.round(priceValue * 100);
            await setPaymentConfig(priceInPaise, "INR");
            await loadPaymentConfig();
            alert("Payment configuration saved successfully!");
        } catch (err) {
            console.error("Error saving price:", err);
            alert("Failed to save payment configuration");
        } finally {
            setSavingPrice(false);
        }
    };

    const loadSettings = async () => {
        try {
            setSettingsLoading(true);
            const data = await getAllSettings();
            setSettings(data.settings || []);
        } catch (err) {
            console.error("Error loading settings:", err);
        } finally {
            setSettingsLoading(false);
        }
    };

    const handleAddLabel = async (category) => {
        const label = newLabels[category]?.trim();
        if (!label) return;

        try {
            await addSettingLabel(category, label);
            setNewLabels({ ...newLabels, [category]: "" });
            await loadSettings();
        } catch (err) {
            console.error("Error adding label:", err);
            alert(err.response?.data?.detail || "Failed to add label");
        }
    };

    const handleRemoveLabel = async (category, label) => {
        if (!window.confirm(`Remove label "${label}" from ${category}?`)) return;

        try {
            await removeSettingLabel(category, label);
            await loadSettings();
        } catch (err) {
            console.error("Error removing label:", err);
            alert(err.response?.data?.detail || "Failed to remove label");
        }
    };

    const handleCreateOrganization = async () => {
        if (!orgName || !adminEmail) {
            setError("Organization name and admin email are required");
            return;
        }

        try {
            setCreating(true);
            setError("");
            const result = await createOrganization(orgName, adminEmail, adminPassword || null);
            setCreatedOrg(result);
            await loadOrganizations();
        } catch (err) {
            console.error("Error creating organization:", err);
            setError(err.response?.data?.detail || "Failed to create organization");
        } finally {
            setCreating(false);
        }
    };

    const handleDeleteOrganization = async (orgId, orgName) => {
        if (!window.confirm(`Are you sure you want to delete "${orgName}"? This will delete ALL data for this organization.`)) {
            return;
        }

        try {
            await deleteOrganization(orgId);
            await loadOrganizations();
            alert("Organization deleted successfully");
        } catch (err) {
            console.error("Error deleting organization:", err);
            alert(err.response?.data?.detail || "Failed to delete organization");
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('user');
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        navigate("/login");
    };

    const resetModal = () => {
        setShowCreateModal(false);
        setOrgName("");
        setAdminEmail("");
        setAdminPassword("");
        setError("");
        setCreatedOrg(null);
    };

    // Loading state
    if (checking) {
        return (
            <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "#fafbfc" }}>
                <div style={{ textAlign: "center", color: "#6b7280" }}>Verifying SuperAdmin access...</div>
            </div>
        );
    }

    // Access denied
    if (accessDenied) {
        return (
            <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "#fafbfc" }}>
                <div style={{ textAlign: "center", maxWidth: 400, padding: 40 }}>
                    <div style={{ fontSize: 64, marginBottom: 16 }}>🔐</div>
                    <h1 style={{ fontSize: 24, fontWeight: 700, color: "#111827", marginBottom: 12 }}>Access Denied</h1>
                    <p style={{ fontSize: 15, color: "#6b7280", marginBottom: 24 }}>
                        Only SuperAdmin users can access this area.
                    </p>
                    <button
                        onClick={() => navigate("/login")}
                        style={{
                            padding: "10px 24px",
                            background: "#2563eb",
                            color: "#fff",
                            border: "none",
                            borderRadius: 8,
                            fontWeight: 500,
                            cursor: "pointer",
                        }}
                    >
                        Back to Login
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div style={{ display: "flex", height: "100vh", background: "#fafbfc" }}>
            {/* Sidebar */}
            <div
                style={{
                    width: 280,
                    background: "#fff",
                    borderRight: "1px solid #e5e7eb",
                    display: "flex",
                    flexDirection: "column",
                    boxShadow: "2px 0 8px rgba(0,0,0,0.03)",
                }}
            >
                {/* Header */}
                <div style={{ padding: "24px 20px", borderBottom: "1px solid #e5e7eb" }}>
                    <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
                        <img
                            src={process.env.PUBLIC_URL + "/favicon.svg"}
                            alt="Course Copilot Logo"
                            style={{ width: 32, height: 32, borderRadius: 6, marginRight: 12 }}
                        />
                        <div>
                            <div style={{ fontWeight: 600, fontSize: 18, color: "#111827" }}>
                                SuperAdmin Panel
                            </div>
                            <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
                                Course Copilot
                            </div>
                        </div>
                    </div>
                </div>

                {/* Nav */}
                <div style={{ flex: 1, padding: "16px 12px", overflowY: "auto" }}>
                    <div
                        onClick={() => { setActiveTab("organizations"); loadOrganizations(); }}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            padding: "12px 16px",
                            marginBottom: 4,
                            borderRadius: 8,
                            cursor: "pointer",
                            background: activeTab === "organizations" ? "#eff6ff" : "transparent",
                            color: activeTab === "organizations" ? "#2563eb" : "#6b7280",
                            fontWeight: activeTab === "organizations" ? 600 : 500,
                            fontSize: 15,
                            transition: "all 0.2s ease",
                        }}
                        onMouseEnter={(e) => {
                            if (activeTab !== "organizations") {
                                e.currentTarget.style.background = "#f9fafb";
                            }
                        }}
                        onMouseLeave={(e) => {
                            if (activeTab !== "organizations") {
                                e.currentTarget.style.background = "transparent";
                            }
                        }}
                    >
                        <FiHome style={{ fontSize: 20, marginRight: 12 }} /> Organizations
                    </div>
                    <div
                        onClick={() => { setActiveTab("payment"); loadPaymentConfig(); }}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            padding: "12px 16px",
                            marginBottom: 4,
                            borderRadius: 8,
                            cursor: "pointer",
                            background: activeTab === "payment" ? "#eff6ff" : "transparent",
                            color: activeTab === "payment" ? "#2563eb" : "#6b7280",
                            fontWeight: activeTab === "payment" ? 600 : 500,
                            fontSize: 15,
                            transition: "all 0.2s ease",
                        }}
                        onMouseEnter={(e) => {
                            if (activeTab !== "payment") {
                                e.currentTarget.style.background = "#f9fafb";
                            }
                        }}
                        onMouseLeave={(e) => {
                            if (activeTab !== "payment") {
                                e.currentTarget.style.background = "transparent";
                            }
                        }}
                    >
                        <FiDollarSign style={{ fontSize: 20, marginRight: 12 }} /> Payment Configuration
                    </div>
                    <div
                        onClick={() => { setActiveTab("settings"); loadSettings(); }}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            padding: "12px 16px",
                            borderRadius: 8,
                            cursor: "pointer",
                            background: activeTab === "settings" ? "#eff6ff" : "transparent",
                            color: activeTab === "settings" ? "#2563eb" : "#6b7280",
                            fontWeight: activeTab === "settings" ? 600 : 500,
                            fontSize: 15,
                            transition: "all 0.2s ease",
                        }}
                        onMouseEnter={(e) => {
                            if (activeTab !== "settings") {
                                e.currentTarget.style.background = "#f9fafb";
                            }
                        }}
                        onMouseLeave={(e) => {
                            if (activeTab !== "settings") {
                                e.currentTarget.style.background = "transparent";
                            }
                        }}
                    >
                        <FiTag style={{ fontSize: 20, marginRight: 12 }} /> Setting Labels
                    </div>
                </div>

                {/* Logout */}
                <div style={{ padding: "16px 12px", borderTop: "1px solid #e5e7eb" }}>
                    <button
                        onClick={handleLogout}
                        style={{
                            width: "100%",
                            display: "flex",
                            alignItems: "center",
                            padding: "12px 16px",
                            borderRadius: 8,
                            cursor: "pointer",
                            background: "transparent",
                            border: "1px solid #e5e7eb",
                            color: "#6b7280",
                            fontWeight: 500,
                            fontSize: 15,
                            transition: "all 0.2s ease",
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.background = "#fef2f2";
                            e.currentTarget.style.color = "#dc2626";
                            e.currentTarget.style.borderColor = "#fecaca";
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = "transparent";
                            e.currentTarget.style.color = "#6b7280";
                            e.currentTarget.style.borderColor = "#e5e7eb";
                        }}
                    >
                        <FiLogOut style={{ fontSize: 20, marginRight: 12 }} /> Logout
                    </button>
                </div>
            </div>

            {/* Main Content */}
            <div style={{ flex: 1, padding: "32px 40px", overflowY: "auto" }}>
                <div style={{ maxWidth: 1000, margin: "0 auto" }}>
                    {activeTab === "organizations" && (
                        <>
                            {/* Organizations Header */}
                            <div style={{ marginBottom: 32 }}>
                                <h1 style={{ fontSize: 28, fontWeight: 700, color: "#111827", margin: 0, marginBottom: 8 }}>Organizations</h1>
                                <p style={{ fontSize: 15, color: "#6b7280", margin: 0 }}>
                                    Manage organizations and their admin credentials
                                </p>
                            </div>

                            {/* Organizations List Card */}
                            <div
                                style={{
                                    background: "#fff",
                                    borderRadius: 12,
                                    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                                    overflow: "hidden",
                                }}
                            >
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "20px 24px", borderBottom: "1px solid #e5e7eb" }}>
                                    <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0 }}>Organization List ({organizations.length})</h2>
                                    <button
                                        onClick={() => setShowCreateModal(true)}
                                        style={{
                                            display: "flex",
                                            alignItems: "center",
                                            padding: "8px 16px",
                                            background: "#2563eb",
                                            color: "#fff",
                                            border: "none",
                                            borderRadius: 6,
                                            fontWeight: 500,
                                            fontSize: 14,
                                            cursor: "pointer",
                                        }}
                                    >
                                        <FiPlus style={{ marginRight: 8 }} /> Create Organization
                                    </button>
                                </div>
                                {loading ? (
                                    <div style={{ padding: 40, textAlign: "center", color: "#6b7280" }}>Loading...</div>
                                ) : organizations.length === 0 ? (
                                    <div style={{ padding: 60, textAlign: "center" }}>
                                        <FiUsers style={{ fontSize: 48, color: "#d1d5db", marginBottom: 16 }} />
                                        <p style={{ color: "#6b7280", margin: 0 }}>No organizations yet</p>
                                    </div>
                                ) : (
                                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                                        <thead>
                                            <tr style={{ borderBottom: "1px solid #e5e7eb", background: "#f9fafb" }}>
                                                <th style={{ padding: "14px 24px", textAlign: "left", color: "#6b7280", fontWeight: 500, fontSize: 13 }}>Organization</th>
                                                <th style={{ padding: "14px 24px", textAlign: "left", color: "#6b7280", fontWeight: 500, fontSize: 13 }}>Admin Email</th>
                                                <th style={{ padding: "14px 24px", textAlign: "left", color: "#6b7280", fontWeight: 500, fontSize: 13 }}>Users</th>
                                                <th style={{ padding: "14px 24px", textAlign: "left", color: "#6b7280", fontWeight: 500, fontSize: 13 }}>Created</th>
                                                <th style={{ padding: "14px 24px", textAlign: "right", color: "#6b7280", fontWeight: 500, fontSize: 13 }}>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {organizations.map((org) => (
                                                <tr key={org._id} style={{ borderBottom: "1px solid #e5e7eb" }}>
                                                    <td style={{ padding: "16px 24px" }}>
                                                        <div style={{ fontWeight: 600, color: "#111827" }}>{org.name}</div>
                                                        <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>{org.database_name}</div>
                                                    </td>
                                                    <td style={{ padding: "16px 24px", color: "#6b7280" }}>{org.admin_email}</td>
                                                    <td style={{ padding: "16px 24px", color: "#6b7280" }}>{org.user_count || 0}</td>
                                                    <td style={{ padding: "16px 24px", color: "#6b7280", fontSize: 13 }}>
                                                        {new Date(org.created_at).toLocaleDateString()}
                                                    </td>
                                                    <td style={{ padding: "16px 24px", textAlign: "right" }}>
                                                        <button
                                                            onClick={() => handleDeleteOrganization(org._id, org.name)}
                                                            style={{
                                                                padding: "8px 12px",
                                                                background: "#fef2f2",
                                                                color: "#dc2626",
                                                                border: "none",
                                                                borderRadius: 6,
                                                                cursor: "pointer",
                                                            }}
                                                        >
                                                            <FiTrash2 />
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                )}
                            </div>
                        </>
                    )}

                    {activeTab === "payment" && (
                        <>
                            {/* Payment Config Header */}
                            <div style={{ marginBottom: 32 }}>
                                <h1 style={{ fontSize: 28, fontWeight: 700, color: "#111827", margin: 0, marginBottom: 8 }}>Payment Configuration</h1>
                                <p style={{ fontSize: 15, color: "#6b7280", margin: 0 }}>
                                    Set the price per user for all organizations
                                </p>
                            </div>

                            {/* Payment Config Card */}
                            <div
                                style={{
                                    background: "#fff",
                                    borderRadius: 12,
                                    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                                    padding: 24,
                                    maxWidth: 500,
                                }}
                            >
                                <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0, marginBottom: 20 }}>
                                    Price Settings
                                </h2>
                                <div style={{ marginBottom: 24 }}>
                                    <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 8 }}>
                                        Price per User (₹)
                                    </label>
                                    <div style={{ display: "flex", gap: 12 }}>
                                        <input
                                            type="number"
                                            value={priceInput}
                                            onChange={(e) => setPriceInput(e.target.value)}
                                            placeholder="e.g., 500"
                                            min="0"
                                            step="1"
                                            style={{
                                                flex: 1,
                                                padding: "10px 12px",
                                                border: "1px solid #e5e7eb",
                                                borderRadius: 8,
                                                color: "#111827",
                                                fontSize: 15,
                                                boxSizing: "border-box",
                                            }}
                                        />
                                        <button
                                            onClick={handleSavePrice}
                                            disabled={savingPrice}
                                            style={{
                                                padding: "10px 20px",
                                                background: savingPrice ? "#9ca3af" : "#2563eb",
                                                color: "#fff",
                                                border: "none",
                                                borderRadius: 8,
                                                fontWeight: 500,
                                                cursor: savingPrice ? "not-allowed" : "pointer",
                                            }}
                                        >
                                            {savingPrice ? "Saving..." : "Save"}
                                        </button>
                                    </div>
                                </div>

                                {paymentConfig && paymentConfig.configured && (
                                    <div style={{
                                        padding: 16,
                                        background: "#f0fdf4",
                                        borderRadius: 8,
                                        border: "1px solid #bbf7d0",
                                    }}>
                                        <div style={{ fontSize: 13, color: "#6b7280", marginBottom: 8 }}>Current Configuration</div>
                                        <div style={{ fontSize: 24, fontWeight: 700, color: "#16a34a" }}>
                                            ₹{(paymentConfig.price_per_user_paise / 100).toFixed(2)}
                                            <span style={{ fontSize: 14, fontWeight: 400, color: "#6b7280", marginLeft: 8 }}>per user</span>
                                        </div>
                                        {paymentConfig.updated_at && (
                                            <div style={{ fontSize: 12, color: "#6b7280", marginTop: 8 }}>
                                                Last updated: {new Date(paymentConfig.updated_at).toLocaleString()}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {paymentConfig && !paymentConfig.configured && (
                                    <div style={{
                                        padding: 16,
                                        background: "#fef2f2",
                                        borderRadius: 8,
                                        border: "1px solid #fecaca",
                                        color: "#dc2626",
                                        fontSize: 14,
                                    }}>
                                        Payment not configured yet. Set a price above.
                                    </div>
                                )}
                            </div>
                        </>
                    )}

                    {activeTab === "settings" && (
                        <>
                            {/* Settings Header */}
                            <div style={{ marginBottom: 32 }}>
                                <h1 style={{ fontSize: 28, fontWeight: 700, color: "#111827", margin: 0, marginBottom: 8 }}>Setting Labels</h1>
                                <p style={{ fontSize: 15, color: "#6b7280", margin: 0 }}>
                                    Manage setting labels for all organizations
                                </p>
                            </div>

                            {/* Settings Content */}
                            {settingsLoading ? (
                                <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>Loading...</div>
                            ) : settings.length === 0 ? (
                                <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>No settings found</div>
                            ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                                    {settings.map((setting) => (
                                        <div
                                            key={setting._id}
                                            style={{
                                                background: "#fff",
                                                borderRadius: 12,
                                                boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                                                padding: 24,
                                            }}
                                        >
                                            <h3 style={{ fontSize: 16, fontWeight: 600, color: "#111827", margin: "0 0 16px" }}>
                                                {formatCategoryName(setting.category)}
                                            </h3>

                                            {/* Add new label */}
                                            <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
                                                <input
                                                    type="text"
                                                    placeholder="New label..."
                                                    value={newLabels[setting.category] || ""}
                                                    onChange={(e) => setNewLabels({ ...newLabels, [setting.category]: e.target.value })}
                                                    onKeyPress={(e) => e.key === "Enter" && handleAddLabel(setting.category)}
                                                    style={{
                                                        flex: 1,
                                                        padding: "10px 14px",
                                                        border: "1px solid #e5e7eb",
                                                        borderRadius: 8,
                                                        color: "#111827",
                                                        fontSize: 14,
                                                        boxSizing: "border-box",
                                                    }}
                                                />
                                                <button
                                                    onClick={() => handleAddLabel(setting.category)}
                                                    style={{
                                                        padding: "10px 16px",
                                                        background: "#2563eb",
                                                        color: "#fff",
                                                        border: "none",
                                                        borderRadius: 8,
                                                        cursor: "pointer",
                                                        display: "flex",
                                                        alignItems: "center",
                                                        gap: 6,
                                                        fontWeight: 500,
                                                    }}
                                                >
                                                    <FiPlus /> Add
                                                </button>
                                            </div>

                                            {/* Labels list */}
                                            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                                                {(setting.options || []).map((option) => (
                                                    <div
                                                        key={option}
                                                        style={{
                                                            display: "flex",
                                                            alignItems: "center",
                                                            gap: 8,
                                                            padding: "6px 12px",
                                                            background: "#f3f4f6",
                                                            border: "1px solid #e5e7eb",
                                                            borderRadius: 20,
                                                            color: "#374151",
                                                            fontSize: 13,
                                                        }}
                                                    >
                                                        <span>{option}</span>
                                                        <button
                                                            onClick={() => handleRemoveLabel(setting.category, option)}
                                                            style={{
                                                                background: "none",
                                                                border: "none",
                                                                color: "#dc2626",
                                                                cursor: "pointer",
                                                                padding: 2,
                                                                display: "flex",
                                                            }}
                                                            title="Remove label"
                                                        >
                                                            <FiTrash2 size={14} />
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </>
                    )}
                </div>
            </div>

            {/* Create Organization Modal */}
            {showCreateModal && (
                <div
                    style={{
                        position: "fixed",
                        inset: 0,
                        background: "rgba(0,0,0,0.5)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        zIndex: 1000,
                    }}
                    onClick={resetModal}
                >
                    <div
                        style={{
                            background: "#fff",
                            borderRadius: 12,
                            padding: 24,
                            width: 480,
                            maxWidth: "90%",
                            boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {createdOrg ? (
                            // Success state
                            <>
                                <div style={{ textAlign: "center", marginBottom: 20 }}>
                                    <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
                                    <h2 style={{ color: "#111827", margin: 0, fontSize: 20, fontWeight: 600 }}>Organization Created!</h2>
                                </div>
                                <div style={{ background: "#f9fafb", borderRadius: 8, padding: 16, marginBottom: 20 }}>
                                    <div style={{ marginBottom: 12 }}>
                                        <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>Organization Name</div>
                                        <div style={{ color: "#111827", fontWeight: 500 }}>{createdOrg.org_name}</div>
                                    </div>
                                    <div style={{ marginBottom: 12 }}>
                                        <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>Admin Email</div>
                                        <div style={{ color: "#111827", fontWeight: 500 }}>{createdOrg.admin_email}</div>
                                    </div>
                                    <div>
                                        <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>Password</div>
                                        <div style={{ color: "#2563eb", fontFamily: "monospace", fontSize: 13, background: "#f3f4f6", padding: "8px 12px", borderRadius: 6 }}>{createdOrg.admin_password}</div>
                                    </div>
                                </div>
                                <div style={{
                                    padding: 12,
                                    background: "#fef3c7",
                                    border: "1px solid #fcd34d",
                                    borderRadius: 8,
                                    marginBottom: 16,
                                    display: "flex",
                                    alignItems: "flex-start",
                                    gap: 8
                                }}>
                                    <span style={{ fontSize: 16 }}>⚠️</span>
                                    <div style={{ fontSize: 13, color: "#92400e" }}>
                                        <strong>Important:</strong> Please save this password securely. It will not be shown again.
                                    </div>
                                </div>
                                <p style={{ color: "#6b7280", fontSize: 14, marginBottom: 20, textAlign: "center" }}>
                                    The admin can now login at <strong>/admin</strong> with these credentials.
                                </p>
                                <button
                                    onClick={resetModal}
                                    style={{
                                        width: "100%",
                                        padding: "12px",
                                        background: "#2563eb",
                                        color: "#fff",
                                        border: "none",
                                        borderRadius: 8,
                                        fontWeight: 500,
                                        cursor: "pointer",
                                    }}
                                >
                                    Done
                                </button>
                            </>
                        ) : (
                            // Create form
                            <>
                                <h2 style={{ color: "#111827", margin: "0 0 20px", fontSize: 20, fontWeight: 600 }}>Create Organization</h2>

                                {error && (
                                    <div style={{ padding: 12, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, color: "#dc2626", marginBottom: 16, fontSize: 14 }}>
                                        {error}
                                    </div>
                                )}

                                <div style={{ marginBottom: 16 }}>
                                    <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>Organization Name *</label>
                                    <input
                                        type="text"
                                        value={orgName}
                                        onChange={(e) => setOrgName(e.target.value)}
                                        disabled={creating}
                                        placeholder="e.g., Acme University"
                                        style={{
                                            width: "100%",
                                            padding: "10px 12px",
                                            border: "1px solid #e5e7eb",
                                            borderRadius: 8,
                                            color: "#111827",
                                            fontSize: 15,
                                            boxSizing: "border-box",
                                        }}
                                    />
                                </div>

                                <div style={{ marginBottom: 16 }}>
                                    <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>Admin Email *</label>
                                    <input
                                        type="email"
                                        value={adminEmail}
                                        onChange={(e) => setAdminEmail(e.target.value)}
                                        disabled={creating}
                                        placeholder="admin@organization.com"
                                        style={{
                                            width: "100%",
                                            padding: "10px 12px",
                                            border: "1px solid #e5e7eb",
                                            borderRadius: 8,
                                            color: "#111827",
                                            fontSize: 15,
                                            boxSizing: "border-box",
                                        }}
                                    />
                                </div>

                                <div style={{ marginBottom: 24 }}>
                                    <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>Admin Password (optional)</label>
                                    <div style={{ position: "relative" }}>
                                        <input
                                            type={showPassword ? "text" : "password"}
                                            value={adminPassword}
                                            onChange={(e) => setAdminPassword(e.target.value)}
                                            disabled={creating}
                                            placeholder="Leave blank to auto-generate"
                                            style={{
                                                width: "100%",
                                                padding: "10px 40px 10px 12px",
                                                border: "1px solid #e5e7eb",
                                                borderRadius: 8,
                                                color: "#111827",
                                                fontSize: 15,
                                                boxSizing: "border-box",
                                            }}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword(!showPassword)}
                                            style={{
                                                position: "absolute",
                                                right: 12,
                                                top: "50%",
                                                transform: "translateY(-50%)",
                                                background: "none",
                                                border: "none",
                                                color: "#6b7280",
                                                cursor: "pointer",
                                            }}
                                        >
                                            {showPassword ? <FiEyeOff /> : <FiEye />}
                                        </button>
                                    </div>
                                </div>

                                <div style={{ display: "flex", gap: 12 }}>
                                    <button
                                        onClick={resetModal}
                                        disabled={creating}
                                        style={{
                                            flex: 1,
                                            padding: "12px",
                                            background: "#f3f4f6",
                                            color: "#374151",
                                            border: "none",
                                            borderRadius: 8,
                                            fontWeight: 500,
                                            cursor: creating ? "not-allowed" : "pointer",
                                        }}
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        onClick={handleCreateOrganization}
                                        disabled={creating}
                                        style={{
                                            flex: 1,
                                            padding: "12px",
                                            background: creating ? "#9ca3af" : "#2563eb",
                                            color: "#fff",
                                            border: "none",
                                            borderRadius: 8,
                                            fontWeight: 500,
                                            cursor: creating ? "not-allowed" : "pointer",
                                        }}
                                    >
                                        {creating ? "Creating..." : "Create Organization"}
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
