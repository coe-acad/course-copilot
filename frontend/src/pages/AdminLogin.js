import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import LoadingSpinner from "../components/LoadingSpinner";
import { login } from "../services/auth";
import { getAllSettings } from "../services/admin";

export default function AdminLogin() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      // Login user
      await login(email, password);
      
      // Check if user has admin access
      try {
        await getAllSettings();
        // If successful, user has admin role
        navigate("/admin");
      } catch (adminError) {
        if (adminError.response?.status === 403) {
          setError("Access denied. You don't have admin privileges.");
          // Logout the user
          localStorage.removeItem('user');
          localStorage.removeItem('token');
          localStorage.removeItem('refresh_token');
        } else {
          throw adminError;
        }
      }
    } catch (err) {
      setError(err.detail || err.response?.data?.detail || "Login failed. Please check credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f7f7f7", display: "flex", justifyContent: "center", alignItems: "center" }}>
      <div style={{
        background: "#fff", borderRadius: 16, boxShadow: "0 4px 24px #0002", padding: 40,
        minWidth: 370, maxWidth: 380, margin: 24, display: "flex", flexDirection: "column", alignItems: "center"
      }}>
        {/* Back Button */}
        <button
          onClick={() => navigate("/login")}
          style={{
            alignSelf: "flex-start",
            marginBottom: 16,
            padding: "6px 12px",
            background: "#f3f4f6",
            border: "1px solid #e5e7eb",
            borderRadius: 6,
            fontSize: 14,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          Back
        </button>

        {/* App Icon and Title */}
        <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
          <img
            src={process.env.PUBLIC_URL + "/favicon.svg"}
            alt="Course Copilot Logo"
            style={{ width: 36, height: 36, borderRadius: 8, marginRight: 12, boxShadow: "0 2px 8px #0001" }}
          />
          <span style={{ fontWeight: 600, fontSize: 20, color: "#222" }}>Admin Panel</span>
        </div>

        <p style={{ fontSize: 14, color: "#6b7280", marginBottom: 24, textAlign: "center" }}>
          Sign in with your admin credentials
        </p>

        {/* Email/Password Form */}
        {loading ? (
          <LoadingSpinner />
        ) : (
          <form onSubmit={handleSubmit} style={{ width: "100%" }}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontWeight: 500, fontSize: 14, color: "#444" }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                disabled={loading}
                style={{ width: "100%", height: 40, padding: "0 12px", border: "1px solid #ddd", borderRadius: 6, marginTop: 6, fontSize: 15, boxSizing: "border-box" }}
              />
            </div>
            <div style={{ marginBottom: 8, position: "relative" }}>
              <label style={{ fontWeight: 500, fontSize: 14, color: "#444" }}>Password</label>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                disabled={loading}
                style={{ width: "100%", height: 40, padding: "0 12px", border: "1px solid #ddd", borderRadius: 6, marginTop: 6, fontSize: 15, boxSizing: "border-box" }}
              />
              <span
                style={{
                  position: "absolute", right: 12, top: 36, fontSize: 13, color: "#2563eb",
                  cursor: "pointer", userSelect: "none", fontWeight: 500
                }}
                onClick={() => setShowPassword(s => !s)}
              >
                {showPassword ? "HIDE" : "SHOW"}
              </span>
            </div>

            {/* Error Display */}
            {error && (
              <div style={{ 
                color: "#dc2626", 
                marginBottom: 16, 
                fontSize: 14,
                padding: "10px 12px",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 6,
              }}>
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%", background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                color: "#fff",
                border: "none", borderRadius: 8, padding: "12px 0",
                fontWeight: 600, fontSize: 17,
                cursor: loading ? "not-allowed" : "pointer", 
                boxShadow: "0 2px 8px rgba(102, 126, 234, 0.25)",
                marginTop: 8,
              }}
            >
              Sign in to Admin Panel
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

