import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { FaUserCircle } from "react-icons/fa";
import { logout } from "../services/auth";
import Modal from "../components/Modal";
import { FaRegStar } from "react-icons/fa";
import { fetchCourses, createCourse } from "../services/course";

export default function Courses() {
  const navigate = useNavigate();
  const [showModal, setShowModal] = useState(false);
  const [courseName, setCourseName] = useState("");
  const [courseDesc, setCourseDesc] = useState("");
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("token")) {
      navigate("/login");
    }
  }, [navigate]);

  useEffect(() => {
    const loadCourses = async () => {
      setLoading(true);
      try {
        const data = await fetchCourses();
        setCourses(data);
      } catch (err) {
        setError("Failed to fetch courses");
      } finally {
        setLoading(false);
      }
    };
    loadCourses();
  }, [showModal]);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleCreate = () => setShowModal(true);
  const handleClose = () => setShowModal(false);
  const handleGetStarted = async () => {
    if (!courseName.trim() || !courseDesc.trim()) return;
    setLoading(true);
    setError("");
    try {
      await createCourse({ name: courseName, description: courseDesc });
      setShowModal(false);
      setCourseName("");
      setCourseDesc("");
      // Refresh courses
      const data = await fetchCourses();
      setCourses(data);
      // Optionally, navigate to dashboard for the new course
      navigate("/dashboard");
    } catch (err) {
      setError("Failed to create course");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "#fff", display: "flex", flexDirection: "column", height: '100vh', overflow: 'hidden' }}>
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
          <div style={{ background: "#2563eb", color: "#fff", borderRadius: 12, width: 40, height: 40, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 22, marginRight: 14, boxShadow: '0 2px 8px #2563eb22' }}>
            C
          </div>
          <span style={{ fontWeight: 700, fontSize: 22, color: "#222", letterSpacing: 0.5 }}>Creators Copilot</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <button
            onClick={handleCreate}
            style={{
              background: '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              padding: '10px 26px',
              fontWeight: 600,
              fontSize: 16,
              boxShadow: '0 2px 8px #2563eb22',
              cursor: 'pointer',
              transition: 'background 0.2s, box-shadow 0.2s',
            }}
            onMouseOver={e => {
              e.currentTarget.style.background = '#174ea6';
              e.currentTarget.style.boxShadow = '0 4px 16px #2563eb33';
            }}
            onMouseOut={e => {
              e.currentTarget.style.background = '#2563eb';
              e.currentTarget.style.boxShadow = '0 2px 8px #2563eb22';
            }}
          >
            Add Course
          </button>
          <button
            onClick={handleLogout}
            style={{ display: "flex", alignItems: "center", gap: 8, background: "none", border: "none", color: "#222", fontWeight: 500, fontSize: 16, cursor: "pointer", padding: 0 }}
          >
            <FaUserCircle style={{ fontSize: 26, color: "#2563eb" }} /> Logout
          </button>
        </div>
      </div>
      {/* Scrollable Courses List Grid */}
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>Loading...</div>
        ) : courses.length === 0 ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <button
              style={{ padding: "10px 22px", borderRadius: 6, border: "none", background: "#1680ea", color: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}
              onClick={handleCreate}
            >
              Create Course
            </button>
          </div>
        ) : (
          <div
            style={{
              flex: 1,
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '32px',
              padding: '48px 4vw',
              alignItems: 'stretch',
              maxWidth: '1040px',
              margin: '0 auto',
            }}
          >
            {courses.map((course, idx) => (
              <div
                key={course.id || idx}
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
                  transition: 'box-shadow 0.2s, transform 0.2s',
                  border: '1.5px solid #e3e8f0',
                  margin: 0,
                }}
                onClick={() => {
                  localStorage.setItem('currentCourseId', course.id || course.courseId);
                  localStorage.setItem('currentCourseTitle', course.name || course.title);
                  navigate('/dashboard');
                }}
                onMouseOver={e => {
                  e.currentTarget.style.boxShadow = '0 8px 32px #2563eb22';
                  e.currentTarget.style.transform = 'scale(1.04)';
                }}
                onMouseOut={e => {
                  e.currentTarget.style.boxShadow = '0 4px 24px #2563eb11';
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                {course.name || course.title}
              </div>
            ))}
          </div>
        )}
      </div>
      <Modal open={showModal} onClose={handleClose} modalStyle={{ minWidth: 0, maxWidth: 600, width: '100%', borderRadius: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 24, marginBottom: 24 }}>Create Course</div>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>Course Name</div>
          <input
            type="text"
            placeholder="e.g. Introduction to Python"
            value={courseName}
            onChange={e => setCourseName(e.target.value)}
            style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", fontSize: 15, borderRadius: 6, border: "1px solid #ccc", marginBottom: 22 }}
            required
          />
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span>About the course</span>
            <button
              type="button"
              style={{ background: "none", border: "none", cursor: "pointer", color: "#2563eb", fontSize: 18, padding: 0 }}
              title="AI Sparkle"
            >
              <FaRegStar style={{ fontSize: 18 }} />
            </button>
          </div>
          <div style={{ position: "relative", marginBottom: 32 }}>
            <textarea
              placeholder="Type here or click the AI Sparkle button to provide details about the course audience (eg. Year 2 Digital Transformation), topics, projects, assessment methods etc."
              value={courseDesc}
              onChange={e => setCourseDesc(e.target.value)}
              style={{ width: "100%", minHeight: 90, boxSizing: "border-box", padding: "10px 12px", fontSize: 15, borderRadius: 6, border: "1px solid #ccc", resize: "vertical" }}
              required
            />
          </div>
          {error && <div style={{ color: "red", marginBottom: 8 }}>{error}</div>}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
            <button onClick={handleClose} style={{ padding: "8px 18px", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}>Close</button>
            <button onClick={handleGetStarted} disabled={!courseName.trim() || !courseDesc.trim() || loading} style={{ padding: "8px 18px", borderRadius: 6, border: "none", background: (!courseName.trim() || !courseDesc.trim() || loading) ? "#bbb" : "#1680ea", color: "#fff", fontWeight: 500, fontSize: 15, cursor: (!courseName.trim() || !courseDesc.trim() || loading) ? "not-allowed" : "pointer" }}>Get Started</button>
          </div>
        </div>
      </Modal>
    </div>
  );
} 