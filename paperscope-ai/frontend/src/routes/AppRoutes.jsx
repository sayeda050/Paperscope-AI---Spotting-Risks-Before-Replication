import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";

// Auth pages
import Index from "../pages/Auth/Index.jsx";
import Login from "../pages/Auth/Login.jsx";
import Register from "../pages/Auth/Register.jsx";
import ForgotPassword from "../pages/Auth/ForgotPassword.jsx";
import ResetPassword from "../pages/Auth/ResetPassword.jsx";

// Main pages
import Dashboard from "../pages/Dashboard/Dashboard.jsx";
import Profile from "../pages/Dashboard/Profile.jsx";
import AnalysisJobs from "../pages/Analysis/AnalysisJobs.jsx";
import AnalysisResult from "../pages/Analysis/AnalysisResult.jsx";
import History from "../pages/Analysis/History.jsx";

/**
 * PrivateRoute: Only allows logged-in users.
 */
function PrivateRoute({ children }) {
  const { isAuthed, initializing } = useAuth();

  if (initializing) {
    return <div className="ps-loading">Verifying session...</div>;
  }

  return isAuthed ? children : <Navigate to="/login" replace />;
}

/**
 * PublicRoute: Prevents logged-in users from seeing auth pages.
 */
function PublicRoute({ children }) {
  const { isAuthed, initializing } = useAuth();

  if (initializing) return null;

  return !isAuthed ? children : <Navigate to="/dashboard" replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      {/* Landing Page */}
      <Route path="/" element={<Index />} />

      {/* Public Auth Routes */}
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
      <Route
        path="/forgot-password"
        element={
          <PublicRoute>
            <ForgotPassword />
          </PublicRoute>
        }
      />
      <Route
        path="/reset-password"
        element={
          <PublicRoute>
            <ResetPassword />
          </PublicRoute>
        }
      />

      {/* Protected Routes */}
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <Dashboard />
          </PrivateRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <PrivateRoute>
            <Profile />
          </PrivateRoute>
        }
      />
      <Route
        path="/analysis/jobs"
        element={
          <PrivateRoute>
            <AnalysisJobs />
          </PrivateRoute>
        }
      />
      <Route
        path="/analysis/result"
        element={
          <PrivateRoute>
            <AnalysisResult />
          </PrivateRoute>
        }
      />
      <Route
        path="/history"
        element={
          <PrivateRoute>
            <History />
          </PrivateRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}