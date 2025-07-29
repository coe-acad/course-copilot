import React from "react";
import { FaUserCircle } from "react-icons/fa";

export default function CoursesLayout({ onAddCourse, onLogout, courses, loading }) {
  return (
    <>
      {/* Header Bar */}
      <div style={{
        height: 64,
        minHeight: 64,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        borderBottom: "1px solid #e5eaf2",
        padding: "0 32px",
        position: 'sticky',
        top: 0,
        background: '#fff',
        zIndex: 10,
        boxShadow: '0 2px 12px #2563eb0a',
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{
            background: "#2563eb",
            color: "#fff",
            borderRadius: 12,
            width: 40,
            height: 40,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            fontSize: 22,
            marginRight: 14,
            boxShadow: '0 2px 8px #2563eb22'
          }}>
            C
          </div>
          <span style={{ fontWeight: 700, fontSize: 22, color: "#222", letterSpacing: 0.5 }}>Creators Copilot</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <button
            onClick={onAddCourse}
            style={{
              background: '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '10px 26px',
              fontWeight: 600,
              fontSize: 16,
              boxShadow: '0 2px 8px #2563eb22',
              cursor: 'pointer'
            }}
          >
            Add Course
          </button>
          <button
            onClick={onLogout}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              background: "none",
              border: "none",
              color: "#222",
              fontWeight: 500,
              fontSize: 16,
              cursor: "pointer",
              padding: 0
            }}
          >
            <FaUserCircle style={{ fontSize: 26, color: "#2563eb" }} /> Logout
          </button>
        </div>
      </div>

      {/* Course Grid */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>Loading...</div>
        ) : courses.length === 0 ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, color: "#666", fontWeight: 500, padding: "1em" }}>
            No courses available.
          </div>
        ) : (
          <div style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '32px',
            padding: '48px 4vw',
            alignItems: 'stretch',
            maxWidth: '1040px',
            margin: '0 auto'
          }}>
            {courses.map((course, idx) => (
              <div
                key={idx}
                style={{
                  background: '#fff',
                  borderRadius: 18,
                  boxShadow: '0 4px 24px #2563eb11',
                  padding: '28px 18px',
                  minHeight: 120,
                  fontWeight: 600,
                  fontSize: 20,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  border: '1.5px solid #e3e8f0'
                }}
              >
                {course.name || "Course Title"}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
