import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import LoadingSpinner from "../components/LoadingSpinner";
import { register } from "../services/auth";

export default function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess(false);

    // Validate passwords match
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      setLoading(false);
      return;
    }

    // Validate password length
    if (password.length < 6) {
      setError("Password must be at least 6 characters long");
      setLoading(false);
      return;
    }

    try {
      // Real registration API call
      const result = await register(email, password, name);
      
      if (result.success) {
        setSuccess(true);
        // Automatically log in after successful registration
        setTimeout(() => navigate("/courses"), 1500);
      } else {
        setError(result.error || "Registration failed. Please try again.");
      }
    } catch (error) {
      console.error("Registration error:", error);
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#f7f7f7", display: "flex", justifyContent: "center", alignItems: "center" }}>
      <div style={{ background: "#fff", borderRadius: 16, boxShadow: "0 4px 24px #0002", padding: 40, minWidth: 370, maxWidth: 380, margin: 24, display: "flex", flexDirection: "column", alignItems: "center" }}>
        {/* App Icon and Title */}
        <div style={{ display: "flex", alignItems: "center", marginBottom: 24 }}>
          <div style={{ background: "#2563eb", color: "#fff", borderRadius: 8, width: 36, height: 36, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 22, marginRight: 12 }}>
            C
          </div>
          <span style={{ fontWeight: 600, fontSize: 20, color: "#222" }}>Creators Copilot</span>
        </div>

        <h2 style={{ marginBottom: 24, color: "#222", fontSize: 24, fontWeight: 600 }}>Create Account</h2>

        {loading ? (
          <LoadingSpinner />
        ) : (
          <form onSubmit={handleSubmit} style={{ width: "100%" }}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontWeight: 500, fontSize: 14, color: "#444" }}>Full Name</label>
              <input
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                disabled={loading}
                style={{ width: "100%", padding: "10px 12px", border: "1px solid #ddd", borderRadius: 6, marginTop: 6, fontSize: 15 }}
                placeholder="Enter your full name"
              />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ fontWeight: 500, fontSize: 14, color: "#444" }}>Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                disabled={loading}
                style={{ width: "100%", padding: "10px 12px", border: "1px solid #ddd", borderRadius: 6, marginTop: 6, fontSize: 15 }}
                placeholder="Enter your email"
              />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ fontWeight: 500, fontSize: 14, color: "#444" }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                disabled={loading}
                style={{ width: "100%", padding: "10px 12px", border: "1px solid #ddd", borderRadius: 6, marginTop: 6, fontSize: 15 }}
                placeholder="Create a password"
              />
            </div>

            <div style={{ marginBottom: 18 }}>
              <label style={{ fontWeight: 500, fontSize: 14, color: "#444" }}>Confirm Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                required
                disabled={loading}
                style={{ width: "100%", padding: "10px 12px", border: "1px solid #ddd", borderRadius: 6, marginTop: 6, fontSize: 15 }}
                placeholder="Confirm your password"
              />
            </div>

            {error && <div style={{ color: "red", marginBottom: 8, fontSize: 14 }}>{error}</div>}
            
            <button
              type="submit"
              disabled={loading}
              style={{ width: "100%", background: "#2563eb", color: "#fff", border: "none", borderRadius: 8, padding: "12px 0", fontWeight: 600, fontSize: 17, cursor: loading ? "not-allowed" : "pointer", boxShadow: "0 1px 2px #0001" }}
            >
              Create Account
            </button>
          </form>
        )}

        {success && (
          <div style={{ color: "green", marginTop: 16, fontSize: 14, textAlign: "center" }}>
            Registration successful! Redirecting to courses...
          </div>
        )}

        <div style={{ marginTop: 24, textAlign: "center", fontSize: 14, color: "#666" }}>
          Already have an account?{" "}
          <Link to="/login" style={{ color: "#2563eb", textDecoration: "none", fontWeight: 500 }}>
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}