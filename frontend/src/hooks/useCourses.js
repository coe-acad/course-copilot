import { useState } from "react";
import { useNavigate } from "react-router-dom";

export function useCourses() {
  const [showModal, setShowModal] = useState(false);
  const [courseName, setCourseName] = useState("");
  const [courseDesc, setCourseDesc] = useState("");
  
  // TODO: Replace dummy courses list with data fetched from backend
  const [courses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, ] = useState("");

  const navigate = useNavigate();

  const handleLogout = () => {
    // TODO: Implement logout logic
    // - clear tokens or session data
    // - optionally call backend logout API
    // - redirect to login page
  };

  const handleGetStarted = () => {
    if (!courseName.trim() || !courseDesc.trim()) return;

    setLoading(true);

    // TODO: Replace this mock logic with real backend API call
    // Example:
    // const response = await createCourse({ name: courseName, description: courseDesc });
    // localStorage.setItem("currentCourseId", response.id);
    // localStorage.setItem("currentCourseTitle", response.name);

    setTimeout(() => {
      localStorage.setItem("currentCourseTitle", courseName);
      localStorage.setItem("currentCourseId", "mock-id");

      // TODO: Only navigate after successful backend response
      navigate("/dashboard");
      setLoading(false);
    }, 1000);
  };

  return {
    showModal, setShowModal,
    courseName, setCourseName,
    courseDesc, setCourseDesc,
    handleLogout, handleGetStarted,
    courses, loading, error
  };
}
