import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { login, isSuperAdmin } from "../services/auth";

export default function SuperAdminLogin() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    // Check if already logged in as superadmin
    useEffect(() => {
        if (isSuperAdmin()) {
            navigate("/superadmin");
        }
    }, [navigate]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError("");

        try {
            const userData = await login(email, password);

            if (userData.isSuperAdmin) {
                navigate("/superadmin");
            } else {
                setError("This account does not have SuperAdmin access.");
                // Clear the stored data since they're not a superadmin
                localStorage.removeItem('user');
                localStorage.removeItem('token');
                localStorage.removeItem('refresh_token');
            }
        } catch (err) {
            setError(err.detail || "Login failed. Please check credentials.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: "100vh",
            background: "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            padding: 20,
        }}>
            <div style={{
                background: "#1e293b",
                borderRadius: 16,
                boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
                padding: 40,
                width: "100%",
                maxWidth: 420,
                border: "1px solid #334155",
            }}>
                {/* Header */}
                <div style={{ textAlign: "center", marginBottom: 32 }}>
                    <div style={{
                        width: 64,
                        height: 64,
                        background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
                        borderRadius: 16,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        margin: "0 auto 16px",
                        boxShadow: "0 10px 40px -10px rgba(59, 130, 246, 0.5)",
                    }}>
                        {/* Crown Icon */}
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                            <path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7z" />
                            <path d="M3 20h18" />
                        </svg>
                    </div>
                    <h1 style={{
                        fontSize: 24,
                        fontWeight: 700,
                        color: "#f1f5f9",
                        margin: "0 0 8px",
                    }}>SuperAdmin Portal</h1>
                    <p style={{
                        fontSize: 14,
                        color: "#64748b",
                        margin: 0,
                    }}>Sign in to access system administration</p>
                </div>

                {/* Error Display */}
                {error && (
                    <div style={{
                        padding: 12,
                        background: "#7f1d1d",
                        border: "1px solid #991b1b",
                        borderRadius: 8,
                        color: "#fca5a5",
                        marginBottom: 20,
                        fontSize: 14,
                        textAlign: "center",
                    }}>
                        {error}
                    </div>
                )}

                {/* Login Form */}
                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: 20 }}>
                        <label style={{
                            display: "block",
                            fontSize: 13,
                            fontWeight: 500,
                            color: "#94a3b8",
                            marginBottom: 8,
                        }}>Email Address</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            disabled={loading}
                            placeholder="superadmin@example.com"
                            style={{
                                width: "100%",
                                padding: "12px 16px",
                                background: "#0f172a",
                                border: "1px solid #334155",
                                borderRadius: 8,
                                color: "#f1f5f9",
                                fontSize: 15,
                                boxSizing: "border-box",
                                transition: "border-color 0.2s",
                            }}
                            onFocus={(e) => e.target.style.borderColor = "#3b82f6"}
                            onBlur={(e) => e.target.style.borderColor = "#334155"}
                        />
                    </div>

                    <div style={{ marginBottom: 24 }}>
                        <label style={{
                            display: "block",
                            fontSize: 13,
                            fontWeight: 500,
                            color: "#94a3b8",
                            marginBottom: 8,
                        }}>Password</label>
                        <div style={{ position: "relative" }}>
                            <input
                                type={showPassword ? "text" : "password"}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                disabled={loading}
                                placeholder="••••••••"
                                style={{
                                    width: "100%",
                                    padding: "12px 50px 12px 16px",
                                    background: "#0f172a",
                                    border: "1px solid #334155",
                                    borderRadius: 8,
                                    color: "#f1f5f9",
                                    fontSize: 15,
                                    boxSizing: "border-box",
                                    transition: "border-color 0.2s",
                                }}
                                onFocus={(e) => e.target.style.borderColor = "#3b82f6"}
                                onBlur={(e) => e.target.style.borderColor = "#334155"}
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
                                    color: "#64748b",
                                    cursor: "pointer",
                                    padding: 4,
                                }}
                            >
                                {showPassword ? (
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                                        <line x1="1" y1="1" x2="23" y2="23" />
                                    </svg>
                                ) : (
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                        <circle cx="12" cy="12" r="3" />
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        style={{
                            width: "100%",
                            padding: "14px",
                            background: loading
                                ? "#475569"
                                : "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
                            color: "#fff",
                            border: "none",
                            borderRadius: 8,
                            fontWeight: 600,
                            fontSize: 16,
                            cursor: loading ? "not-allowed" : "pointer",
                            transition: "all 0.3s ease",
                            boxShadow: loading ? "none" : "0 10px 40px -10px rgba(59, 130, 246, 0.5)",
                        }}
                    >
                        {loading ? "Signing in..." : "Sign in to Dashboard"}
                    </button>
                </form>

                {/* Back Link */}
                <div style={{ marginTop: 24, textAlign: "center" }}>
                    <button
                        onClick={() => navigate("/login")}
                        style={{
                            background: "none",
                            border: "none",
                            color: "#64748b",
                            fontSize: 14,
                            cursor: "pointer",
                            textDecoration: "underline",
                        }}
                    >
                        ← Back to main login
                    </button>
                </div>
            </div>
        </div>
    );
}
