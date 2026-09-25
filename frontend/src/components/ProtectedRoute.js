import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { isAuthenticated } from "../services/auth";

export default function ProtectedRoute() {
    // If user is authenticated, render the child component (page)
    // Otherwise, redirect immediately to /login
    if (!isAuthenticated()) {
        return <Navigate to="/login" replace />;
    }

    return <Outlet />;
}
