import React, { useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Courses from "./pages/Courses";
import ErrorBoundary from "./components/ErrorBoundary";
import ProtectedRoute from "./components/ProtectedRoute";
import NotFound from "./pages/NotFound";
import ForgotPassword from "./pages/ForgotPassword";
import AssetStudio from './pages/AssetStudio';
import Evaluation from './pages/Evaluation';
import { initKeycloak, setupTokenRefresh } from "./services/keycloak";

function App() {
  // Initialize Keycloak on app load to handle OAuth callbacks
  useEffect(() => {
    const initializeKeycloak = async () => {
      try {
        // Initialize Keycloak - this will handle OAuth callback if present
        await initKeycloak();
        setupTokenRefresh();
      } catch (error) {
        console.error("Failed to initialize Keycloak:", error);
      }
    };
    
    initializeKeycloak();
  }, []);

  return (
    <ErrorBoundary>
        <Router>
          <Routes>
            <Route path="/" element={<Navigate to="/login" />} />
            <Route
              path="/courses"
              element={
                <ProtectedRoute>
                  <Courses />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/studio/:feature"
              element={
                <ProtectedRoute>
                  <AssetStudio />
                </ProtectedRoute>
              }
            />
            <Route
              path="/evaluation"
              element={
                <ProtectedRoute>
                  <Evaluation />
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<Login />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Router>
    </ErrorBoundary>
  );
}

export default App;
