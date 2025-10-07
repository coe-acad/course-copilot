import React, { useState } from "react";
import Modal from "./Modal";

export default function LMSLoginModal({ open, onClose, onLoginSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate inputs
    if (!email || !password) {
      setError("Please enter both email and password");
      return;
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      setError("Please enter a valid email address");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const token = localStorage.getItem("token");
      
      // ========================================
      // BACKEND INTEGRATION REQUIRED
      // ========================================
      // 
      // ENDPOINT: POST /api/login-lms
      // 
      // REQUEST HEADERS:
      // - Authorization: Bearer <user_auth_token>
      // - Content-Type: application/json
      // 
      // REQUEST BODY:
      // {
      //   "email": "user@example.com",
      //   "password": "userpassword"
      // }
      // 
      // EXPECTED SUCCESS RESPONSE (200):
      // {
      //   "message": "Successfully logged into LMS",
      //   "data": {
      //     "token": "lms_jwt_token_from_platform",
      //     "user": {
      //       "id": "lms_user_id",
      //       "email": "user@example.com",
      //       "name": "User Name"
      //     }
      //   }
      // }
      // 
      // EXPECTED ERROR RESPONSES:
      // - 400: { "detail": "Email and password are required" }
      // - 401: { "detail": "LMS authentication failed" }
      // - 422: { "detail": "Invalid email format" }
      // - 500: { "detail": "LMS base URL is not configured" }
      // - 503: { "detail": "Connection error - Could not connect to LMS server" }
      // 
      // BACKEND IMPLEMENTATION NOTES:
      // 1. Validate email format and required fields
      // 2. Extract user_id from Authorization token (already implemented)
      // 3. Call LMS platform authentication endpoint
      // 4. Handle LMS-specific response format
      // 5. Return standardized response format
      // 6. Implement proper error handling for all scenarios
      // 
      const response = await fetch(
        `${process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'}/api/login-lms`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            email: email.trim(),
            password: password
          })
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error("❌ LMS Login Error:", errorData);
        const errorMessage = errorData.detail || errorData.message || 'Login failed. Please check your credentials.';
        throw new Error(errorMessage);
      }

      const data = await response.json();
      
      // Store LMS cookies (for session-based auth) and user data
      const lmsCookies = data.cookies || "";
      const lmsUser = data.data?.user || data.user || {};
      const lmsToken = data.token || data.data?.token || "";  // Some APIs might also return a token
      
      localStorage.setItem("lms_cookies", lmsCookies);
      localStorage.setItem("lms_user", JSON.stringify(lmsUser));
      if (lmsToken) {
        localStorage.setItem("lms_token", lmsToken);
      }
      
      console.log("✅ LMS Login Success:", { 
        cookies: lmsCookies ? lmsCookies.substring(0, 50) + "..." : "none",
        token: lmsToken ? lmsToken.substring(0, 30) + "..." : "none",
        user: lmsUser 
      });
      
      // Check if in mock mode
      const isMockMode = data.message?.includes("MOCK MODE");
      if (isMockMode) {
        console.log("⚠️ Running in MOCK MODE - LMS_BASE_URL not configured in backend");
      }
      
      // Call success callback
      if (onLoginSuccess) {
        onLoginSuccess(data);
      }

      // Close modal and reset form
      setEmail("");
      setPassword("");
      setError("");
      onClose();
    } catch (err) {
      console.error('LMS login error:', err);
      setError(err.message || 'Failed to login to LMS. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setEmail("");
      setPassword("");
      setError("");
      onClose();
    }
  };

  if (!open) return null;

  return (
    <Modal open={open} onClose={handleClose}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Header */}
        <div>
          <div style={{ fontWeight: 700, fontSize: 24, marginBottom: 8, color: "#111827" }}>
            🔐 Login to LMS
          </div>
          <div style={{ fontSize: 14, color: "#6b7280" }}>
            Enter your LMS credentials to export content
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Error Message */}
          {error && (
            <div style={{
              background: "#fee2e2",
              border: "1px solid #fecaca",
              color: "#b91c1c",
              padding: "12px 14px",
              borderRadius: 8,
              fontSize: 14,
              display: "flex",
              alignItems: "center",
              gap: 8
            }}>
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* Email Field */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontWeight: 600, fontSize: 14, color: "#374151" }}>
              Email Address <span style={{ color: "#ef4444" }}>*</span>
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
              disabled={loading}
              style={{
                padding: "10px 14px",
                border: "1px solid #d1d5db",
                borderRadius: 8,
                fontSize: 14,
                outline: "none",
                transition: "border-color 0.2s",
                background: loading ? "#f9fafb" : "#fff",
                cursor: loading ? "not-allowed" : "text"
              }}
              onFocus={(e) => e.target.style.borderColor = "#2563eb"}
              onBlur={(e) => e.target.style.borderColor = "#d1d5db"}
            />
          </div>

          {/* Password Field */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <label style={{ fontWeight: 600, fontSize: 14, color: "#374151" }}>
              Password <span style={{ color: "#ef4444" }}>*</span>
            </label>
            <div style={{ position: "relative" }}>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "10px 40px 10px 14px",
                  border: "1px solid #d1d5db",
                  borderRadius: 8,
                  fontSize: 14,
                  outline: "none",
                  transition: "border-color 0.2s",
                  background: loading ? "#f9fafb" : "#fff",
                  cursor: loading ? "not-allowed" : "text",
                  boxSizing: "border-box"
                }}
                onFocus={(e) => e.target.style.borderColor = "#2563eb"}
                onBlur={(e) => e.target.style.borderColor = "#d1d5db"}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                disabled={loading}
                style={{
                  position: "absolute",
                  right: 10,
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  cursor: loading ? "not-allowed" : "pointer",
                  fontSize: 18,
                  color: "#6b7280",
                  padding: 4
                }}
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "👁️" : "👁️‍🗨️"}
              </button>
            </div>
          </div>

          {/* Info Box */}
          <div style={{
            background: "#fef3c7",
            border: "1px solid #fcd34d",
            borderRadius: 8,
            padding: "10px 12px",
            fontSize: 13,
            color: "#92400e",
            display: "flex",
            gap: 8
          }}>
            <span>⚠️</span>
            <div>
              <strong>DEVELOPMENT MODE:</strong> LMS connection not configured. Any email/password will work for testing the UI flow. 
              When LMS_BASE_URL is configured, this will authenticate with your actual LMS platform.
            </div>
          </div>

          {/* Buttons */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
            <button
              type="button"
              onClick={handleClose}
              disabled={loading}
              style={{
                padding: "10px 20px",
                borderRadius: 8,
                border: "1px solid #d1d5db",
                background: "#fff",
                color: "#374151",
                fontWeight: 500,
                fontSize: 14,
                cursor: loading ? "not-allowed" : "pointer",
                opacity: loading ? 0.5 : 1,
                transition: "all 0.2s"
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !email || !password}
              style={{
                padding: "10px 24px",
                borderRadius: 8,
                border: "none",
                background: (loading || !email || !password) ? "#94a3b8" : "#2563eb",
                color: "#fff",
                fontWeight: 600,
                fontSize: 14,
                cursor: (loading || !email || !password) ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
                transition: "all 0.2s"
              }}
            >
              {loading ? (
                <>
                  <div style={{
                    width: 16,
                    height: 16,
                    border: "2px solid #fff",
                    borderTop: "2px solid transparent",
                    borderRadius: "50%",
                    animation: "spin 1s linear infinite"
                  }}></div>
                  <span>Logging in...</span>
                </>
              ) : (
                <span>Login to LMS</span>
              )}
            </button>
          </div>
        </form>

        {/* Spinner Animation */}
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </Modal>
  );
}

