import React from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { hasUsableSession, logout } from "../services/auth";

export default function ProtectedRoute() {
    const location = useLocation();

    // Guard every nested route: no usable session -> straight to /login, with the
    // attempted URL remembered so login can send the user back where they aimed.
    //
    // This is a UX/navigation guard only. It is trivially bypassed in a browser,
    // so it is NOT what keeps data safe — every data endpoint on the backend
    // enforces Depends(verify_token) independently.
    if (!hasUsableSession()) {
        logout(); // clear any stale/partial credentials so the app restarts clean
        return <Navigate to="/login" replace state={{ from: location.pathname }} />;
    }

    return <Outlet />;
}
