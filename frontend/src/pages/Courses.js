import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { FaUserCircle } from "react-icons/fa";
import { logout, isAuthenticated } from "../services/auth";
import { fetchCourses, createCourse } from "../services/course";
import Modal from "../components/Modal";
import { FaRegStar } from "react-icons/fa";
import LoadingSpinner from "../components/LoadingSpinner";

export default function Courses() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [showModal, setShowModal] = useState(false);
  const [courseName, setCourseName] = useState("");
  const [courseDesc, setCourseDesc] = useState("");
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    // Handle OAuth callback parameters first
    const success = searchParams.get("success");
    const token = searchParams.get("token");
    const user_id = searchParams.get("user_id");
    const email = searchParams.get("email");
    const name = searchParams.get("name");

    if (success === "true" && token) {
      // Store the authentication data from OAuth callback
      localStorage.setItem("authToken", token);
      localStorage.setItem("user", JSON.stringify({
        id: user_id,
        email: email,
        name: name
      }));
      
      // Clear URL parameters to clean up the URL
      window.history.replaceState({}, document.title, window.location.pathname);
      
      console.log("Google OAuth login successful:", { email, name });
    }

    // Check if user is authenticated (either from OAuth or existing session)
    if (!isAuthenticated()) {
      navigate("/login");
      return;
    }

    loadCourses();
  }, [navigate, searchParams]);

  const loadCourses = async () => {
    try {
      setLoading(true);
      setError("");
      const fetchedCourses = await fetchCourses();
      setCourses(fetchedCourses);
    } catch (error) {
      console.error("Failed to load courses:", error);
      setError("Failed to load courses. Please try again.");
      // Fallback to local storage if API fails
      const stored = JSON.parse(localStorage.getItem("courses")) || [];
      setCourses(stored);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      navigate("/login");
    } catch (error) {
      console.error("Logout failed:", error);
      // Still redirect to login even if backend logout fails
      navigate("/login");
    }
  };

  const handleCreate = () => setShowModal(true);
  const handleClose = () => {
    setShowModal(false);
    setCourseName("");
    setCourseDesc("");
    setError("");
  };

  const handleGetStarted = async () => {
    if (!courseName.trim() || !courseDesc.trim()) return;

    try {
      setCreating(true);
      setError("");

      // Create course via API
      const newCourse = await createCourse({
        name: courseName,
        description: courseDesc,
        year: 2024,
        level: "Beginner"
      });

      // Update local state
      setCourses(prev => [...prev, newCourse]);
      
      // Store current course info
      localStorage.setItem("currentCourseTitle", newCourse.title);
      localStorage.setItem("currentCourseId", newCourse.courseId);
      
      handleClose();
      navigate("/dashboard");
    } catch (error) {
      console.error("Failed to create course:", error);
      setError(error.message || "Failed to create course. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  const handleCourseClick = (course) => {
    localStorage.setItem("currentCourseTitle", course.title);
    localStorage.setItem("currentCourseId", course.courseId);
    navigate("/dashboard");
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#fff", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#fff", display: "flex", flexDirection: "column" }}>
      {/* Header Bar */}
      <div style={{ height: 40, display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #eee", padding: "0 16px" }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <div style={{ background: "#2563eb", color: "#fff", borderRadius: 8, width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 16, marginRight: 8 }}>
            C
          </div>
          <span style={{ fontWeight: 500, fontSize: 15, color: "#222" }}>Creators Copilot</span>
        </div>
        <button
          onClick={handleLogout}
          style={{ display: "flex", alignItems: "center", gap: 8, background: "none", border: "none", color: "#222", fontWeight: 500, fontSize: 15, cursor: "pointer", padding: 0 }}
        >
          <FaUserCircle style={{ fontSize: 22, color: "#2563eb" }} /> Logout
        </button>
      </div>

      {/* Error Message */}
      {error && (
        <div style={{ 
          background: "#fee", 
          color: "#c33", 
          padding: "12px 16px", 
          margin: "16px", 
          borderRadius: 6, 
          fontSize: 14 
        }}>
          {error}
        </div>
      )}

      {/* Courses List or Centered Create Button */}
      {courses.length === 0 ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <button
            style={{ padding: "10px 22px", borderRadius: 6, border: "none", background: "#1680ea", color: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}
            onClick={handleCreate}
          >
            Create Course
          </button>
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexWrap: 'wrap', gap: 24, padding: '40px 5vw' }}>
          {courses.map((course, idx) => (
            <div
              key={course.courseId || idx}
              style={{
                background: '#f5f7fa',
                borderRadius: 12,
                boxShadow: '0 1px 4px #0001',
                padding: '16px 24px',
                minWidth: 180,
                minHeight: 96,
                height: 96,
                fontWeight: 600,
                fontSize: 18,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                transition: 'box-shadow 0.15s',
                border: '2px solid transparent',
              }}
              onClick={() => handleCourseClick(course)}
              onMouseOver={e => e.currentTarget.style.boxShadow = '0 4px 16px #2563eb22'}
              onMouseOut={e => e.currentTarget.style.boxShadow = '0 1px 4px #0001'}
            >
              {course.title}
            </div>
          ))}
        </div>
      )}

      <Modal open={showModal} onClose={handleClose} modalStyle={{ minWidth: 0, maxWidth: 600, width: '100%', borderRadius: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 24, marginBottom: 24 }}>Create Course</div>
          
          {error && (
            <div style={{ 
              background: "#fee", 
              color: "#c33", 
              padding: "8px 12px", 
              marginBottom: "16px", 
              borderRadius: 6, 
              fontSize: 14 
            }}>
              {error}
            </div>
          )}

          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>Course Name</div>
          <input
            type="text"
            placeholder="e.g. Introduction to Python"
            value={courseName}
            onChange={e => setCourseName(e.target.value)}
            style={{ width: "100%", boxSizing: "border-box", padding: "10px 12px", fontSize: 15, borderRadius: 6, border: "1px solid #ccc", marginBottom: 22 }}
            required
            disabled={creating}
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
              disabled={creating}
            />
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
            <button 
              onClick={handleClose} 
              disabled={creating}
              style={{ 
                padding: "8px 18px", 
                borderRadius: 6, 
                border: "1px solid #bbb", 
                background: "#fff", 
                fontWeight: 500, 
                fontSize: 15, 
                cursor: creating ? "not-allowed" : "pointer",
                opacity: creating ? 0.6 : 1
              }}
            >
              Close
            </button>
            <button 
              onClick={handleGetStarted} 
              disabled={!courseName.trim() || !courseDesc.trim() || creating} 
              style={{ 
                padding: "8px 18px", 
                borderRadius: 6, 
                border: "none", 
                background: (!courseName.trim() || !courseDesc.trim() || creating) ? "#bbb" : "#1680ea", 
                color: "#fff", 
                fontWeight: 500, 
                fontSize: 15, 
                cursor: (!courseName.trim() || !courseDesc.trim() || creating) ? "not-allowed" : "pointer" 
              }}
            >
              {creating ? "Creating..." : "Get Started"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
} 