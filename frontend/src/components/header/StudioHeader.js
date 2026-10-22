import React from "react";
import { FaUserCircle } from "react-icons/fa";
import { FiArrowLeft } from "react-icons/fi";
import { useNavigate } from "react-router-dom";


export default function StudioHeader({
  onSettings,
  onLogout,
  onBack
}) {
  const navigate = useNavigate();
  const courseTitle = localStorage.getItem("currentCourseTitle");

  return (
    <header
      style={{
        height: 64,
        minHeight: 64,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 32px",
        background: "#fff",
        borderBottom: "1px solid #e5eaf2",
        boxShadow: "0 2px 12px #2563eb0a",
        position: "relative",
        zIndex: 10,
      }}
    >
      {/* Left: Brand + current course */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, minWidth: 0 }}>
        <div
          style={{ display: "flex", alignItems: "center", gap: 16, cursor: "pointer", flexShrink: 0 }}
          onClick={() => navigate('/courses')}
        >
          <img
            src="/favicon.svg"
            alt="Course Copilot Logo"
            style={{
              width: 40,
              height: 40,
              marginRight: 14,
            }}
          />
          <span style={{ fontWeight: 700, fontSize: 22, color: "#222", letterSpacing: 0.5 }}>Course Copilot</span>
        </div>
        {courseTitle && (
          <>
            <span style={{ color: "#cbd5e1", fontSize: 22, fontWeight: 300 }}>/</span>
            <span
              title={courseTitle}
              style={{ fontSize: 16, fontWeight: 500, color: "#6b7280", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 360 }}
            >
              {courseTitle}
            </span>
          </>
        )}
      </div>

      {/* Right: Buttons */}
      <div style={{ display: "flex", alignItems: "center", gap: 18, flexShrink: 0 }}>
        <button
          className="cc-section-btn"
          onClick={() => navigate(-1)}
          style={btnStyle}
        >
          <FiArrowLeft /> Back to course
        </button>

        {/* Logout */}
        <button
          title="Logout"
          onClick={onLogout}
          style={{ display: "flex", alignItems: "center", gap: 8, background: "none", border: "none", color: "#222", fontWeight: 500, fontSize: 16, cursor: "pointer", padding: 0 }}
        >
          <FaUserCircle style={{ fontSize: 26, color: "#2563eb" }} /> Logout
        </button>
      </div>
    </header>
  );
}

const btnStyle = {
  height: 38,
  padding: "0 18px",
  borderRadius: 8,
  border: "1px solid #ddd",
  background: "#fff",
  color: "#222",
  cursor: "pointer",
  fontSize: 15,
  fontWeight: 500,
  display: "flex",
  alignItems: "center",
  gap: 8,
  transition: "background 0.15s, border-color 0.15s, color 0.15s",
};
