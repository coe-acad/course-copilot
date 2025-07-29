import React from "react";
import Modal from "./Modal";
import { FaRegStar } from "react-icons/fa";

export default function CourseModal({
  open, onClose,
  courseName, setCourseName,
  courseDesc, setCourseDesc,
  onSubmit, loading, error
}) {
  return (
    <Modal open={open} onClose={onClose} modalStyle={{ minWidth: 0, maxWidth: 600, width: '100%', borderRadius: 12 }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: 24, marginBottom: 24 }}>Create Course</div>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>Course Name</div>
        <input
          type="text"
          placeholder="e.g. Introduction to Python"
          value={courseName}
          onChange={e => setCourseName(e.target.value)}
          style={{ width: "100%", padding: "10px 12px", fontSize: 15, borderRadius: 6, border: "1px solid #ccc", marginBottom: 22 }}
          required
        />
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8, display: "flex", justifyContent: "space-between" }}>
          <span>About the course</span>
          <button
            type="button"
            style={{ background: "none", border: "none", cursor: "pointer", color: "#2563eb", fontSize: 18 }}
            title="AI Sparkle"
          >
            <FaRegStar />
          </button>
        </div>
        <textarea
          placeholder="Describe your course audience, topics, projects etc."
          value={courseDesc}
          onChange={e => setCourseDesc(e.target.value)}
          style={{ width: "100%", minHeight: 90, padding: "10px 12px", fontSize: 15, borderRadius: 6, border: "1px solid #ccc", resize: "vertical", marginBottom: 32 }}
          required
        />
        {error && <div style={{ color: "red", marginBottom: 8 }}>{error}</div>}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <button onClick={onClose} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontSize: 15 }}>Close</button>
          <button onClick={onSubmit} disabled={!courseName.trim() || !courseDesc.trim() || loading}
            style={{ padding: "8px 18px", borderRadius: 6, border: "none", background: (!courseName || !courseDesc || loading) ? "#bbb" : "#1680ea", color: "#fff", fontSize: 15 }}>
            Get Started
          </button>
        </div>
      </div>
    </Modal>
  );
}
