import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { FiUsers, FiFileText, FiTag, FiLogOut, FiDownload, FiTrash2, FiCreditCard, FiCheck } from "react-icons/fi";
import { uploadAdminDocument, getAdminDocuments, downloadAdminDocument, deleteAdminDocument, getAllSettings, addSettingLabel, removeSettingLabel, getAllUsers, updateUserRole, createUser, deleteUser, getPaymentSummary, createPaymentOrder, verifyPayment, getPaymentHistory, getPaymentReceipt } from "../services/admin";

export default function Admin() {
  const [activeTab, setActiveTab] = useState("users");
  const [checking, setChecking] = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const navigate = useNavigate();

  // Verify admin access on mount
  useEffect(() => {
    verifyAdminAccess();
  }, []);

  const verifyAdminAccess = async () => {
    try {
      setChecking(true);
      // Try to fetch admin settings - this will fail if not admin
      await getAllSettings();
      setAccessDenied(false);
    } catch (err) {
      if (err.response?.status === 403) {
        setAccessDenied(true);
      } else if (err.response?.status === 401) {
        // Not logged in, redirect to admin login
        navigate("/admin-login");
      }
    } finally {
      setChecking(false);
    }
  };

  const handleLogout = () => {
    // Clear session and return to login
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    navigate("/login");
  };

  const tabs = [
    { id: "users", label: "User Management", icon: <FiUsers /> },
    { id: "documents", label: "Add Documents", icon: <FiFileText /> },
    { id: "settings", label: "Add Setting Labels", icon: <FiTag /> },
    { id: "payments", label: "Payments", icon: <FiCreditCard /> },
  ];

  // Loading state
  if (checking) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "#fafbfc" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 18, color: "#6b7280" }}>Verifying admin access...</div>
        </div>
      </div>
    );
  }

  // Access denied state
  if (accessDenied) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "#fafbfc" }}>
        <div style={{ textAlign: "center", maxWidth: 400, padding: 40 }}>
          <div style={{ fontSize: 64, marginBottom: 16 }}>🔒</div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "#111827", marginBottom: 12 }}>
            Access Denied
          </h1>
          <p style={{ fontSize: 15, color: "#6b7280", marginBottom: 24 }}>
            You don't have permission to access the admin panel. Only users with admin role can access this area.
          </p>
          <button
            onClick={() => navigate("/admin-login")}
            style={{
              padding: "10px 20px",
              background: "#2563eb",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              fontWeight: 500,
              fontSize: 15,
              cursor: "pointer",
            }}
          >
            Back to Admin Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", background: "#fafbfc" }}>
      {/* Left Sidebar */}
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
        <div
          style={{
            padding: "24px 20px",
            borderBottom: "1px solid #e5e7eb",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
            <img
              src={process.env.PUBLIC_URL + "/favicon.svg"}
              alt="Course Copilot Logo"
              style={{ width: 32, height: 32, borderRadius: 6, marginRight: 12 }}
            />
            <div>
              <div style={{ fontWeight: 600, fontSize: 18, color: "#111827" }}>
                Admin Panel
              </div>
              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
                Course Copilot
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div style={{ flex: 1, padding: "16px 12px", overflowY: "auto" }}>
          {tabs.map((tab) => (
            <div
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: "flex",
                alignItems: "center",
                padding: "12px 16px",
                marginBottom: 4,
                borderRadius: 8,
                cursor: "pointer",
                background: activeTab === tab.id ? "#eff6ff" : "transparent",
                color: activeTab === tab.id ? "#2563eb" : "#6b7280",
                fontWeight: activeTab === tab.id ? 600 : 500,
                fontSize: 15,
                transition: "all 0.2s ease",
              }}
              onMouseEnter={(e) => {
                if (activeTab !== tab.id) {
                  e.currentTarget.style.background = "#f9fafb";
                }
              }}
              onMouseLeave={(e) => {
                if (activeTab !== tab.id) {
                  e.currentTarget.style.background = "transparent";
                }
              }}
            >
              <span style={{ fontSize: 20, marginRight: 12 }}>{tab.icon}</span>
              {tab.label}
            </div>
          ))}
        </div>

        {/* Footer - Logout */}
        <div
          style={{
            padding: "16px 12px",
            borderTop: "1px solid #e5e7eb",
          }}
        >
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
            <FiLogOut style={{ fontSize: 20, marginRight: 12 }} />
            Logout
          </button>
        </div>
      </div>

      {/* Right Content Area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "32px 40px",
        }}
      >
        {activeTab === "users" && <UserManagement />}
        {activeTab === "documents" && <AddDocuments />}
        {activeTab === "settings" && <AddSettingLabels />}
        {activeTab === "payments" && <Payments />}
      </div>
    </div>
  );
}

// User Management Component
function UserManagement() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await getAllUsers();
      setUsers(response.users || []);
    } catch (err) {
      console.error("Error loading users:", err);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAddUser = async () => {
    if (!newUserEmail || !newUserName || !newUserPassword) {
      setCreateError("Name, email and password are required");
      return;
    }

    if (newUserPassword.length < 6) {
      setCreateError("Password must be at least 6 characters");
      return;
    }

    try {
      setCreating(true);
      setCreateError("");
      await createUser(newUserName, newUserEmail, newUserPassword);
      setShowAddUserModal(false);
      setNewUserEmail("");
      setNewUserName("");
      setNewUserPassword("");
      await loadUsers();
      alert("User created successfully!");
    } catch (err) {
      console.error("Error creating user:", err);
      setCreateError(err.response?.data?.detail || "Failed to create user");
    } finally {
      setCreating(false);
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    if (!window.confirm(`Are you sure you want to change this user's role to ${newRole}?`)) {
      return;
    }

    try {
      await updateUserRole(userId, newRole);
      await loadUsers();
      alert("User role updated successfully!");
    } catch (err) {
      console.error("Error updating role:", err);
      alert(err.response?.data?.detail || "Failed to update user role");
    }
  };

  const handleDeleteUser = async (userId, userEmail) => {
    if (!window.confirm(`Are you sure you want to delete user "${userEmail}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await deleteUser(userId);
      await loadUsers();
      alert("User deleted successfully!");
    } catch (err) {
      console.error("Error deleting user:", err);
      alert(err.response?.data?.detail || "Failed to delete user");
    }
  };

  const filteredUsers = users.filter(user =>
    user.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.display_name?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: "#111827", margin: 0, marginBottom: 8 }}>
          User Management
        </h1>
        <p style={{ fontSize: 15, color: "#6b7280", margin: 0 }}>
          Manage users, permissions, and access control
        </p>
      </div>

      {/* Content Card */}
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0 }}>User List ({users.length})</h2>
          <button
            onClick={() => setShowAddUserModal(true)}
            style={{
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
            + Add User
          </button>
        </div>

        {/* Search Bar */}
        <input
          type="text"
          placeholder="Search users by email or name..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            width: "100%",
            padding: "10px 16px",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            fontSize: 15,
            marginBottom: 20,
            boxSizing: "border-box",
          }}
        />

        {loading ? (
          <div style={{ color: "#6b7280", textAlign: "center", padding: "40px 0" }}>
            Loading users...
          </div>
        ) : filteredUsers.length === 0 ? (
          <div style={{ color: "#6b7280", textAlign: "center", padding: "40px 0" }}>
            <FiUsers style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }} />
            <p>No users found</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {filteredUsers.map((user) => (
              <div
                key={user._id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: 16,
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#111827", marginBottom: 4 }}>
                    {user.display_name || "No name"}
                  </div>
                  <div style={{ fontSize: 13, color: "#6b7280" }}>
                    {user.email}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <select
                    value={user.role || "user"}
                    onChange={(e) => handleRoleChange(user._id, e.target.value)}
                    style={{
                      padding: "6px 12px",
                      border: "1px solid #e5e7eb",
                      borderRadius: 6,
                      fontSize: 14,
                      fontWeight: 500,
                      color: user.role === "admin" ? "#2563eb" : "#6b7280",
                      cursor: "pointer",
                    }}
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                  </select>
                  {/* Delete button - uncomment when needed
                  <button
                    onClick={() => handleDeleteUser(user._id, user.email)}
                    style={{
                      padding: "8px 10px",
                      background: "#fef2f2",
                      color: "#dc2626",
                      border: "none",
                      borderRadius: 6,
                      fontSize: 14,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                    }}
                    title="Delete user"
                  >
                    <FiTrash2 size={16} />
                  </button>
                  */}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add User Modal */}
      {showAddUserModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setShowAddUserModal(false)}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 12,
              padding: 24,
              maxWidth: 500,
              width: "90%",
              boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 style={{ fontSize: 20, fontWeight: 600, color: "#111827", margin: 0, marginBottom: 20 }}>
              Add New User
            </h2>

            {createError && (
              <div style={{
                padding: "12px",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 8,
                color: "#dc2626",
                marginBottom: 16,
                fontSize: 14
              }}>
                {createError}
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
                Name
              </label>
              <input
                type="text"
                value={newUserName}
                onChange={(e) => setNewUserName(e.target.value)}
                disabled={creating}
                placeholder="John Doe"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                  fontSize: 15,
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
                Email
              </label>
              <input
                type="email"
                value={newUserEmail}
                onChange={(e) => setNewUserEmail(e.target.value)}
                disabled={creating}
                placeholder="user@example.com"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                  fontSize: 15,
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
                Password
              </label>
              <input
                type="password"
                value={newUserPassword}
                onChange={(e) => setNewUserPassword(e.target.value)}
                disabled={creating}
                placeholder="Minimum 6 characters"
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                  fontSize: 15,
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button
                onClick={() => {
                  setShowAddUserModal(false);
                  setCreateError("");
                  setNewUserEmail("");
                  setNewUserName("");
                  setNewUserPassword("");
                }}
                disabled={creating}
                style={{
                  padding: "10px 20px",
                  background: "#f3f4f6",
                  color: "#374151",
                  border: "none",
                  borderRadius: 8,
                  fontWeight: 500,
                  fontSize: 15,
                  cursor: creating ? "not-allowed" : "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleAddUser}
                disabled={creating}
                style={{
                  padding: "10px 20px",
                  background: creating ? "#9ca3af" : "#2563eb",
                  color: "#fff",
                  border: "none",
                  borderRadius: 8,
                  fontWeight: 500,
                  fontSize: 15,
                  cursor: creating ? "not-allowed" : "pointer",
                }}
              >
                {creating ? "Creating..." : "Create User"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Add Documents Component
function AddDocuments() {
  const [documentTitle, setDocumentTitle] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Load documents on mount
  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError("");
      const response = await getAdminDocuments();
      setDocuments(response.documents || []);
    } catch (err) {
      console.error("Error loading documents:", err);
      // Silently handle errors - just show empty state
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Validate file type
      const allowedTypes = ["application/pdf", "text/plain"];
      const allowedExtensions = [".pdf", ".txt"];
      const fileExtension = "." + file.name.split(".").pop().toLowerCase();

      if (!allowedTypes.includes(file.type) || !allowedExtensions.includes(fileExtension)) {
        setError("Only PDF and TXT files are allowed");
        return;
      }

      // Validate file size (10MB)
      if (file.size > 10 * 1024 * 1024) {
        setError("File size must be less than 10MB");
        return;
      }

      setSelectedFile(file);
      setError("");
    }
  };

  const handleUpload = async () => {
    if (!documentTitle || !selectedFile) {
      setError("Please enter document title and select a file");
      return;
    }

    try {
      setUploading(true);
      setError("");
      await uploadAdminDocument(documentTitle, selectedFile);

      // Reset form
      setDocumentTitle("");
      setSelectedFile(null);

      // Reload documents
      await loadDocuments();

      alert("Document uploaded successfully!");
    } catch (err) {
      console.error("Error uploading document:", err);
      setError("Failed to upload document: " + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (doc) => {
    try {
      await downloadAdminDocument(doc._id, doc.filename);
    } catch (err) {
      console.error("Error downloading document:", err);
      alert("Failed to download document");
    }
  };

  const handleDelete = async (docId) => {
    if (!window.confirm("Are you sure you want to delete this document?")) {
      return;
    }

    try {
      await deleteAdminDocument(docId);
      await loadDocuments();
      alert("Document deleted successfully!");
    } catch (err) {
      console.error("Error deleting document:", err);
      alert("Failed to delete document");
    }
  };

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: "#111827", margin: 0, marginBottom: 8 }}>
          Add Documents
        </h1>
        <p style={{ fontSize: 15, color: "#6b7280", margin: 0 }}>
          Upload and manage system documents
        </p>
      </div>

      {/* Upload Section */}
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
          marginBottom: 20,
        }}
      >
        <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0, marginBottom: 16 }}>
          Upload Document
        </h2>

        {error && (
          <div style={{
            padding: "12px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 8,
            color: "#dc2626",
            marginBottom: 16,
            fontSize: 14
          }}>
            {error}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
            Document Title
          </label>
          <input
            type="text"
            value={documentTitle}
            onChange={(e) => setDocumentTitle(e.target.value)}
            disabled={uploading}
            placeholder="Enter document title..."
            style={{
              width: "100%",
              padding: "10px 12px",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              fontSize: 15,
              boxSizing: "border-box",
            }}
          />
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
            Upload File
          </label>
          <input
            type="file"
            accept=".pdf,.txt"
            onChange={handleFileSelect}
            disabled={uploading}
            style={{ display: "none" }}
            id="file-upload"
          />
          <label
            htmlFor="file-upload"
            style={{
              display: "block",
              border: "2px dashed #d1d5db",
              borderRadius: 8,
              padding: "32px",
              textAlign: "center",
              cursor: uploading ? "not-allowed" : "pointer",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              if (!uploading) {
                e.currentTarget.style.borderColor = "#2563eb";
                e.currentTarget.style.background = "#eff6ff";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "#d1d5db";
              e.currentTarget.style.background = "transparent";
            }}
          >
            <FiFileText style={{ fontSize: 40, color: "#9ca3af", marginBottom: 12 }} />
            <p style={{ margin: 0, color: "#6b7280", fontSize: 14 }}>
              Click to upload or drag and drop
            </p>
            <p style={{ margin: 0, color: "#9ca3af", fontSize: 13, marginTop: 4 }}>
              PDF, TXT up to 10MB
            </p>
          </label>

          {/* Selected File Preview */}
          {selectedFile && (
            <div style={{ marginTop: 12 }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                background: '#f3f4f6',
                borderRadius: 8,
                padding: '10px 12px',
                border: '1px solid #e5e7eb'
              }}>
                <FiFileText style={{ fontSize: 20, color: "#2563eb", marginRight: 10, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: "#111827", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {selectedFile.name}
                  </div>
                  <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.preventDefault();
                    setSelectedFile(null);
                  }}
                  disabled={uploading}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#dc2626",
                    cursor: uploading ? "not-allowed" : "pointer",
                    padding: 4,
                    display: "flex",
                    alignItems: "center",
                    marginLeft: 8
                  }}
                  title="Remove file"
                >
                  <FiTrash2 size={18} />
                </button>
              </div>
            </div>
          )}
        </div>

        <button
          onClick={handleUpload}
          disabled={uploading}
          style={{
            padding: "10px 20px",
            background: uploading ? "#9ca3af" : "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            fontWeight: 500,
            fontSize: 15,
            cursor: uploading ? "not-allowed" : "pointer",
          }}
        >
          {uploading ? "Uploading..." : "Upload Document"}
        </button>
      </div>

      {/* Documents List */}
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        }}
      >
        <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0, marginBottom: 16 }}>
          Uploaded Documents ({documents.length})
        </h2>

        {loading ? (
          <div style={{ color: "#6b7280", textAlign: "center", padding: "40px 0" }}>
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div style={{ color: "#6b7280", textAlign: "center", padding: "40px 0" }}>
            <FiFileText style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }} />
            <p>No documents uploaded yet</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {documents.map((doc) => (
              <div
                key={doc._id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: 16,
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "#f9fafb";
                  e.currentTarget.style.borderColor = "#d1d5db";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.borderColor = "#e5e7eb";
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#111827", marginBottom: 4 }}>
                    {doc.document_title}
                  </div>
                  <div style={{ fontSize: 13, color: "#6b7280" }}>
                    {doc.filename} • {new Date(doc.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    onClick={() => handleDownload(doc)}
                    style={{
                      padding: "8px 12px",
                      background: "#f3f4f6",
                      color: "#374151",
                      border: "none",
                      borderRadius: 6,
                      fontSize: 14,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <FiDownload /> Download
                  </button>
                  <button
                    onClick={() => handleDelete(doc._id)}
                    style={{
                      padding: "8px 12px",
                      background: "#fef2f2",
                      color: "#dc2626",
                      border: "none",
                      borderRadius: 6,
                      fontSize: 14,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    <FiTrash2 /> Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Add Setting Labels Component
function AddSettingLabels() {
  const [category, setCategory] = useState("");
  const [labelName, setLabelName] = useState("");
  const [adding, setAdding] = useState(false);
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await getAllSettings();
      setSettings(response.settings || []);
    } catch (err) {
      console.error("Error loading settings:", err);
      setSettings([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAddLabel = async () => {
    if (!category || !labelName) {
      setError("Please select a category and enter a label name");
      return;
    }

    try {
      setAdding(true);
      setError("");
      await addSettingLabel(category, labelName);
      setLabelName("");
      setCategory("");
      await loadSettings();
      alert("Label added successfully!");
    } catch (err) {
      console.error("Error adding label:", err);
      setError(err.response?.data?.detail || "Failed to add label");
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveLabel = async (cat, label) => {
    if (!window.confirm(`Are you sure you want to remove "${label}" from ${cat}?`)) {
      return;
    }

    try {
      await removeSettingLabel(cat, label);
      await loadSettings();
      alert("Label removed successfully!");
    } catch (err) {
      console.error("Error removing label:", err);
      alert(err.response?.data?.detail || "Failed to remove label");
    }
  };

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: "#111827", margin: 0, marginBottom: 8 }}>
          Add Setting Labels
        </h1>
        <p style={{ fontSize: 15, color: "#6b7280", margin: 0 }}>
          Configure system setting labels and options
        </p>
      </div>

      {/* Add Label Section */}
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
          marginBottom: 20,
        }}
      >
        <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0, marginBottom: 16 }}>
          Add New Label
        </h2>

        {error && (
          <div style={{
            padding: "12px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 8,
            color: "#dc2626",
            marginBottom: 16,
            fontSize: 14
          }}>
            {error}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
            Label Category
          </label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            disabled={adding}
            style={{
              width: "100%",
              padding: "10px 12px",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              fontSize: 15,
              boxSizing: "border-box",
            }}
          >
            <option value="">Select category...</option>
            <option value="course_level">Course Level</option>
            <option value="study_area">Study Area</option>
            <option value="pedagogical_components">Pedagogical Components</option>
          </select>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={{ display: "block", fontSize: 14, fontWeight: 500, color: "#374151", marginBottom: 6 }}>
            Label Name
          </label>
          <input
            type="text"
            value={labelName}
            onChange={(e) => setLabelName(e.target.value)}
            disabled={adding}
            placeholder="Enter label name..."
            style={{
              width: "100%",
              padding: "10px 12px",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              fontSize: 15,
              boxSizing: "border-box",
            }}
          />
        </div>

        <button
          onClick={handleAddLabel}
          disabled={adding}
          style={{
            padding: "10px 20px",
            background: adding ? "#9ca3af" : "#2563eb",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            fontWeight: 500,
            fontSize: 15,
            cursor: adding ? "not-allowed" : "pointer",
          }}
        >
          {adding ? "Adding..." : "Add Label"}
        </button>
      </div>

      {/* Existing Labels */}
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        }}
      >
        <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0, marginBottom: 16 }}>
          Existing Labels
        </h2>

        {loading ? (
          <div style={{ color: "#6b7280", textAlign: "center", padding: "40px 0" }}>
            Loading settings...
          </div>
        ) : settings.length === 0 ? (
          <div style={{ color: "#6b7280", textAlign: "center", padding: "40px 0" }}>
            <FiTag style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }} />
            <p>No labels configured yet</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {settings.map((setting) => (
              <div key={setting._id}>
                <h3 style={{ fontSize: 16, fontWeight: 600, color: "#111827", marginBottom: 12 }}>
                  {setting.label}
                </h3>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {(setting.options || []).map((option) => (
                    <div
                      key={option}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "6px 12px",
                        background: "#f3f4f6",
                        border: "1px solid #e5e7eb",
                        borderRadius: 6,
                        fontSize: 14,
                      }}
                    >
                      <span>{option}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


// Payments Component
function Payments() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [paymentHistory, setPaymentHistoryState] = useState([]);
  const [showReceipt, setShowReceipt] = useState(null);
  const [receiptData, setReceiptData] = useState(null);

  useEffect(() => {
    loadData();
    // Load Razorpay script
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    document.body.appendChild(script);
    return () => {
      document.body.removeChild(script);
    };
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [summaryData, historyData] = await Promise.all([
        getPaymentSummary(),
        getPaymentHistory()
      ]);
      setSummary(summaryData);
      setPaymentHistoryState(historyData.payments || []);
    } catch (err) {
      console.error("Error loading payment data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handlePayNow = async () => {
    try {
      setProcessing(true);

      // Create order
      const orderData = await createPaymentOrder();

      // Open Razorpay checkout
      const options = {
        key: orderData.key_id,
        amount: orderData.amount,
        currency: orderData.currency,
        name: "Course Copilot",
        description: `Payment for ${summary.user_count} users`,
        order_id: orderData.order_id,
        handler: async function (response) {
          try {
            // Verify payment
            await verifyPayment(
              response.razorpay_order_id,
              response.razorpay_payment_id,
              response.razorpay_signature
            );
            alert("Payment successful!");
            loadData();
          } catch (err) {
            console.error("Payment verification failed:", err);
            alert("Payment verification failed. Please contact support.");
          }
        },
        prefill: {
          email: localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')).email : ''
        },
        theme: {
          color: "#2563eb"
        }
      };

      const rzp = new window.Razorpay(options);
      rzp.open();

    } catch (err) {
      console.error("Error creating order:", err);
      alert(err.response?.data?.detail || "Failed to create payment order");
    } finally {
      setProcessing(false);
    }
  };

  const handleViewReceipt = async (paymentId) => {
    try {
      const data = await getPaymentReceipt(paymentId);
      setReceiptData(data.receipt);
      setShowReceipt(true);
    } catch (err) {
      console.error("Error loading receipt:", err);
      alert("Failed to load receipt");
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>
        Loading payment information...
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, color: "#111827", margin: 0, marginBottom: 8 }}>
          Payments
        </h1>
        <p style={{ fontSize: 15, color: "#6b7280", margin: 0 }}>
          Manage organization payments
        </p>
      </div>

      {/* Payment Summary Card */}
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: 32,
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
          marginBottom: 24,
          maxWidth: 500,
        }}
      >
        {!summary?.configured ? (
          <div style={{ textAlign: "center", color: "#6b7280" }}>
            <p>Payment not configured by SuperAdmin.</p>
            <p style={{ fontSize: 14 }}>Please contact your SuperAdmin to set up payment.</p>
          </div>
        ) : (
          <>
            <div style={{ marginBottom: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ color: "#6b7280" }}>Users (excl. admin):</span>
                <span style={{ fontWeight: 600, color: "#111827" }}>{summary.user_count}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ color: "#6b7280" }}>Price per user:</span>
                <span style={{ fontWeight: 600, color: "#111827" }}>₹{(summary.price_per_user_paise / 100).toFixed(2)}</span>
              </div>
              <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: 12, marginTop: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontWeight: 600, color: "#111827", fontSize: 18 }}>Total Amount:</span>
                  <span style={{ fontWeight: 700, color: "#2563eb", fontSize: 24 }}>₹{(summary.total_amount_paise / 100).toFixed(2)}</span>
                </div>
              </div>
            </div>

            <button
              onClick={handlePayNow}
              disabled={processing || summary.user_count === 0}
              style={{
                width: "100%",
                padding: "14px 24px",
                background: processing || summary.user_count === 0 ? "#9ca3af" : "#2563eb",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                fontWeight: 600,
                fontSize: 16,
                cursor: processing || summary.user_count === 0 ? "not-allowed" : "pointer",
              }}
            >
              {processing ? "Processing..." : `Pay Now ₹${(summary.total_amount_paise / 100).toFixed(2)}`}
            </button>
            {summary.user_count === 0 && (
              <p style={{ fontSize: 13, color: "#6b7280", textAlign: "center", marginTop: 12 }}>
                No users to charge. Add users first.
              </p>
            )}
          </>
        )}
      </div>

      {/* Payment History */}
      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        }}
      >
        <h2 style={{ fontSize: 18, fontWeight: 600, color: "#111827", margin: 0, marginBottom: 16 }}>
          Payment History
        </h2>

        {paymentHistory.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>
            <FiCreditCard style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }} />
            <p>No payment history yet</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {paymentHistory.map((payment) => (
              <div
                key={payment._id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: 16,
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: "#111827" }}>
                    ₹{(payment.amount_paise / 100).toFixed(2)}
                  </div>
                  <div style={{ fontSize: 13, color: "#6b7280" }}>
                    {payment.user_count} users • {new Date(payment.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {payment.status === "captured" ? (
                    <>
                      <span style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "4px 12px",
                        background: "#dcfce7",
                        color: "#16a34a",
                        borderRadius: 20,
                        fontSize: 13,
                        fontWeight: 500,
                      }}>
                        <FiCheck size={14} /> Paid
                      </span>
                      <button
                        onClick={() => handleViewReceipt(payment._id)}
                        style={{
                          padding: "6px 12px",
                          background: "#f3f4f6",
                          border: "none",
                          borderRadius: 6,
                          color: "#374151",
                          fontSize: 13,
                          cursor: "pointer",
                        }}
                      >
                        View Receipt
                      </button>
                    </>
                  ) : (
                    <span style={{
                      padding: "4px 12px",
                      background: "#fef3c7",
                      color: "#d97706",
                      borderRadius: 20,
                      fontSize: 13,
                      fontWeight: 500,
                    }}>
                      {payment.status}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Receipt Modal */}
      {showReceipt && receiptData && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={() => setShowReceipt(false)}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 12,
              padding: 32,
              maxWidth: 500,
              width: "90%",
              boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>🧾</div>
              <h2 style={{ fontSize: 20, fontWeight: 600, color: "#111827", margin: 0 }}>
                Payment Receipt
              </h2>
            </div>

            <div style={{ background: "#f9fafb", borderRadius: 8, padding: 20, marginBottom: 24 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ color: "#6b7280" }}>Payment ID:</span>
                <span style={{ fontWeight: 500, color: "#111827", fontFamily: "monospace", fontSize: 12 }}>
                  {receiptData.razorpay_payment_id}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ color: "#6b7280" }}>Organization:</span>
                <span style={{ fontWeight: 500, color: "#111827" }}>{receiptData.org_name}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ color: "#6b7280" }}>Users:</span>
                <span style={{ fontWeight: 500, color: "#111827" }}>{receiptData.user_count}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                <span style={{ color: "#6b7280" }}>Price per user:</span>
                <span style={{ fontWeight: 500, color: "#111827" }}>
                  ₹{(receiptData.price_per_user_paise / 100).toFixed(2)}
                </span>
              </div>
              <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: 12, marginTop: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontWeight: 600, color: "#111827" }}>Total Amount:</span>
                  <span style={{ fontWeight: 700, color: "#2563eb", fontSize: 20 }}>
                    {receiptData.amount_display}
                  </span>
                </div>
              </div>
              <div style={{ marginTop: 16, fontSize: 12, color: "#6b7280" }}>
                Date: {new Date(receiptData.captured_at).toLocaleString()}
              </div>
            </div>

            <button
              onClick={() => setShowReceipt(false)}
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
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
