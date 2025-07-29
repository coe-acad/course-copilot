// src/pages/Courses.js
import React from "react";
import CoursesLayout from "../layouts/CoursesLayout";
import CourseModal from "../components/CourseModal";
import { useCourses } from "../hooks/useCourses";

export default function Courses() {
  const {
    showModal, setShowModal,
    courseName, setCourseName,
    courseDesc, setCourseDesc,
    handleLogout, handleGetStarted,
    courses, loading, error
  } = useCourses();

  return (
    <div style={{ minHeight: "100vh", background: "#fff", display: "flex", flexDirection: "column", height: '100vh', overflow: 'hidden' }}>
      <CoursesLayout
        onAddCourse={() => setShowModal(true)}
        onLogout={handleLogout}
        courses={courses}
        loading={loading}
      />
      <CourseModal
        open={showModal}
        onClose={() => setShowModal(false)}
        courseName={courseName}
        setCourseName={setCourseName}
        courseDesc={courseDesc}
        setCourseDesc={setCourseDesc}
        onSubmit={handleGetStarted}
        loading={loading}
        error={error}
      />
    </div>
  );
}
