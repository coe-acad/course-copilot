import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import Input from "../components/Input";
import Button from "../components/Button";
import { register } from "../services/auth";

export default function Register() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    // backend integration: replace with real registration API call
    if (register(username, password)) {
      setSuccess(true);
      setTimeout(() => navigate("/login"), 1000);
    } else {
      setError("Registration failed");
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: "2rem auto", padding: 24, border: "1px solid #eee", borderRadius: 8 }}>
      <h2>Register</h2>
      <form onSubmit={handleSubmit}>
        <Input label="Username" value={username} onChange={e => setUsername(e.target.value)} required />
        <Input label="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        {error && <div style={{ color: "red", marginBottom: 8 }}>{error}</div>}
        <Button type="submit">Register</Button>
      </form>
      {success && <div style={{ color: "green", marginTop: 8 }}>Registration successful! Redirecting to login...</div>}
      <div style={{ marginTop: 16 }}>
        Already have an account? <Link to="/login">Login</Link>
      </div>
    </div>
  );
}