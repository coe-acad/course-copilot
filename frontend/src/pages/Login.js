import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import LoadingSpinner from "../components/LoadingSpinner";
import { initKeycloak, loginKeycloak, loginWithGoogle, loginDirect, setupTokenRefresh } from "../services/keycloak";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // Initialize Keycloak on component mount
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        setLoading(true);
        // Initialize Keycloak and check if already logged in
        const authenticated = await initKeycloak();
        
        if (authenticated) {
          // User is already authenticated, redirect to courses
          setupTokenRefresh();
          navigate("/courses");
        } else {
          // Not authenticated, stay on login page
          setupTokenRefresh();
        }
      } catch (err) {
        console.error("Keycloak initialization failed:", err);
        setError("Authentication initialization failed. Please refresh the page.");
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();
  }, [navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      // Direct login with email/password (no redirect)
      await loginDirect(email, password);
      // Login successful, redirect to courses
      navigate("/courses");
    } catch (err) {
      console.error("Login error:", err);
      setError(err.message || "Login failed. Please check your credentials.");
      setLoading(false);
    }
  };

  const handleKeycloakLogin = async () => {
    try {
      setLoading(true);
      setError("");
      // Redirect to Keycloak login page
      // Note: loginKeycloak() causes a redirect, so code below won't execute
      await loginKeycloak();
    } catch (err) {
      console.error("Login error:", err);
      setError("Login failed. Please try again.");
      setLoading(false);
    }
  }

  const handleGoogleLogin = async () => {
    try {
      setLoading(true);
      setError("");
      // Redirect to Google login via Keycloak
      await loginWithGoogle();
    } catch (err) {
      console.error("Google login error:", err);
      setError("Google login failed. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#f7f7f7", display: "flex", justifyContent: "center", alignItems: "center" }}>
      <div style={{
        background: "#fff", borderRadius: 16, boxShadow: "0 4px 24px #0002", padding: 40,
        minWidth: 370, maxWidth: 380, margin: 24, display: "flex", flexDirection: "column", alignItems: "center"
      }}>
        {/* App Icon and Title */}
        <div style={{ display: "flex", alignItems: "center", marginBottom: 24 }}>
          <img
            src={process.env.PUBLIC_URL + "/favicon.svg"}
            alt="Course Copilot Logo"
            style={{ width: 36, height: 36, borderRadius: 8, marginRight: 12, boxShadow: "0 2px 8px #0001" }}
          />
          <span style={{ fontWeight: 600, fontSize: 20, color: "#222" }}>Course Copilot</span>
        </div>

        {/* Keycloak Sign-In */}
        <button
          type="button"
          style={{
            width: "100%", background: "#2563eb", color: "#fff", border: "none",
            borderRadius: 6, padding: "10px 0", fontWeight: 500, fontSize: 16,
            cursor: loading ? "not-allowed" : "pointer", boxShadow: "0 1px 2px #0001",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 12
          }}
          disabled={loading}
          onClick={handleKeycloakLogin}
        >
          Sign in with Keycloak
        </button>

        {/* Google Sign-In */}
        <button
          type="button"
          style={{
            width: "100%", background: "#fff", color: "#222", border: "1px solid #ddd",
            borderRadius: 6, padding: "10px 0", fontWeight: 500, fontSize: 16,
            cursor: loading ? "not-allowed" : "pointer", boxShadow: "0 1px 2px #0001",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 24
          }}
          disabled={loading}
          onClick={handleGoogleLogin}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" style={{ marginRight: 4 }}>
            <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/>
            <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/>
            <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957C.348 6.175 0 7.55 0 9s.348 2.825.957 4.039l3.007-2.332z"/>
            <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.293C4.672 5.163 6.656 3.58 9 3.58z"/>
          </svg>
          Sign in with Google
        </button>

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

            {/* Remember me and Forgot password
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
              <label style={{ display: "flex", alignItems: "center", fontSize: 15, color: "#444", fontWeight: 500 }}>
                <input
                  type="checkbox"
                  checked={keepSignedIn}
                  onChange={e => setKeepSignedIn(e.target.checked)}
                  style={{ marginRight: 8, accentColor: "#2563eb" }}
                />
                Keep me signed in
              </label>
              <Link to="/forgot-password" style={{ color: "#2563eb", fontSize: 14, textDecoration: "none", fontWeight: 400 }}>Forgot password?</Link>
            </div> */}

            {/* Error Display */}
            {error && <div style={{ color: "red", marginBottom: 8 }}>{error}</div>}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%", background: "#2563eb", color: "#fff",
                border: "none", borderRadius: 8, padding: "12px 0",
                fontWeight: 600, fontSize: 17,
                cursor: loading ? "not-allowed" : "pointer", boxShadow: "0 1px 2px #0001"
              }}
            >
              Sign in
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
