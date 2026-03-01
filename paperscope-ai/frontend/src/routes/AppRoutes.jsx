import React from 'react';
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";

// Import your pages - matching your folder structure
import Index from "../pages/Auth/Index.jsx";
import Login from "../pages/Auth/Login.jsx";
import Register from "../pages/Auth/Register.jsx";
import Dashboard from "../pages/Dashboard/Dashboard.jsx";

/**
 * PrivateRoute: Only allows logged-in users.
 * It waits for 'initializing' to be false before deciding.
 */
function PrivateRoute({ children }) {
  const { isAuthed, initializing } = useAuth();

  // 1. If we are still checking the cookie, show a blank screen or spinner
  // This prevents the "bounce" back to login
  if (initializing) return <div className="ps-loading">Verifying session...</div>;

  // 2. Only redirect if initializing is DONE and user is definitely not authed
  return isAuthed ? children : <Navigate to="/login" replace />;
}

/**
 * PublicRoute: Prevents logged-in users from seeing Login/Register pages.
 */
function PublicRoute({ children }) {
  const { isAuthed, initializing } = useAuth();

  if (initializing) return null;

  // If already logged in, send them straight to the dashboard
  return !isAuthed ? children : <Navigate to="/dashboard" replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      {/* Landing Page */}
      <Route path="/" element={<Index />} />

      {/* Auth Pages (Protected from logged-in users) */}
      <Route 
        path="/login" 
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        } 
      />
      <Route 
        path="/register" 
        element={
          <PublicRoute>
            <Register />
          </PublicRoute>
        } 
      />

      {/* ✅ Protected Dashboard (Only for logged-in users) */}
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <Dashboard />
          </PrivateRoute>
        }
      />

      {/* Fallback for unknown URLs */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}