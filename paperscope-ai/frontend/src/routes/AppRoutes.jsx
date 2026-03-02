import React from 'react';
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";

// Auth pages
import Index from "../pages/Auth/Index.jsx";
import Login from "../pages/Auth/Login.jsx";
import Register from "../pages/Auth/Register.jsx";
import ForgotPassword from "../pages/Auth/ForgotPassword.jsx";
import ResetPassword from "../pages/Auth/ResetPassword.jsx";

// Dashboard & Profile
import Dashboard from "../pages/Dashboard/Dashboard.jsx";
import Profile from "../pages/Dashboard/Profile.jsx";

// Admin Pages (Combined from both versions)
import AdminDashboard from "../pages/Dashboard/AdminDashboard.jsx";
import AdminPapers from "../pages/Papers/AdminPapers.jsx";
import AdminUsers from "../pages/Dashboard/AdminUsers.jsx";
import AdminJobs from "../pages/Analysis/AdminJobs.jsx";
import AdminResults from "../pages/Dashboard/AdminResults.jsx";
import AdminResultDetail from "../pages/Dashboard/AdminResultDetail.jsx";
import ErrorLogs from "../pages/Dashboard/ErrorLogs.jsx";
import ModelVersions from "../pages/Dashboard/ModelVersions.jsx";

// Analysis & User Paper Pages
import SubmitPaper from "../pages/Papers/SubmitPaper.jsx";
import AnalysisJobs from "../pages/Analysis/AnalysisJobs.jsx";
import AnalysisResult from "../pages/Analysis/AnalysisResult.jsx";
import History from "../pages/Analysis/History.jsx";

function PrivateRoute({ children }) {
  const { isAuthed, initializing } = useAuth();
  if (initializing) return <div className="ps-loading">Verifying session...</div>;
  return isAuthed ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children }) {
  const { isAuthed, initializing } = useAuth();
  if (initializing) return null;
  return !isAuthed ? children : <Navigate to="/dashboard" replace />;
}

export default function AppRoutes() {
  const { user } = useAuth();
  const isAdmin = user?.is_superuser || user?.role === 'ADMIN';

  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<Index />} />
      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
      <Route path="/forgot-password" element={<PublicRoute><ForgotPassword /></PublicRoute>} />
      <Route path="/reset-password" element={<PublicRoute><ResetPassword /></PublicRoute>} />

      {/* User Dashboard Routes */}
      <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/dashboard/submit" element={<PrivateRoute><SubmitPaper /></PrivateRoute>} />
      <Route path="/dashboard/profile" element={<PrivateRoute><Profile /></PrivateRoute>} />
      
      {/* FIXED: Conditionally render AdminJobs if user is Admin, otherwise AnalysisJobs */}
      <Route 
        path="/dashboard/jobs" 
        element={
          <PrivateRoute>
            {isAdmin ? <AdminJobs /> : <AnalysisJobs />}
          </PrivateRoute>
        } 
      />

      <Route path="/dashboard/history" element={<PrivateRoute><History /></PrivateRoute>} />
      <Route path="/dashboard/result/:jobId" element={<PrivateRoute><AnalysisResult /></PrivateRoute>} />

      {/* Admin Routes (Merged Set) */}
      <Route path="/dashboard/admin" element={<PrivateRoute><AdminDashboard /></PrivateRoute>} />
      <Route path="/dashboard/admin/papers" element={<PrivateRoute><AdminPapers /></PrivateRoute>} />
      <Route path="/dashboard/admin/users" element={<PrivateRoute><AdminUsers /></PrivateRoute>} />
      <Route path="/dashboard/admin/jobs" element={<PrivateRoute><AdminJobs /></PrivateRoute>} />
      <Route path="/dashboard/admin/results" element={<PrivateRoute><AdminResults /></PrivateRoute>} />
      <Route path="/dashboard/admin/results/:resultId" element={<PrivateRoute><AdminResultDetail /></PrivateRoute>} />
      <Route path="/dashboard/admin/models" element={<PrivateRoute><ModelVersions /></PrivateRoute>} />
      <Route path="/dashboard/admin/errors" element={<PrivateRoute><ErrorLogs /></PrivateRoute>} />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}