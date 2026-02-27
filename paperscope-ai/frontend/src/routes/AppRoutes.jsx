﻿import React from 'react';
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";

// Import your exact page structure
import Index from "../pages/Auth/Index.jsx";
import Login from "../pages/Auth/Login.jsx";
import Register from "../pages/Auth/Register.jsx";
import Dashboard from "../pages/Dashboard/Dashboard.jsx";
import AnalysisJobs from "../pages/Analysis/AnalysisJobs.jsx";
import AnalysisResult from "../pages/Analysis/AnalysisResult.jsx";
import History from "../pages/Analysis/History.jsx"; // New Import
import Profile from "../pages/Dashboard/Profile.jsx"; // New Import

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
  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />

      <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      
      <Route path="/dashboard/jobs" element={<PrivateRoute><AnalysisJobs /></PrivateRoute>} />
      <Route path="/dashboard/history" element={<PrivateRoute><History /></PrivateRoute>} /> {/* New Route */}
      <Route path="/dashboard/result/:jobId" element={<PrivateRoute><AnalysisResult /></PrivateRoute>} />
      <Route path="/dashboard/profile" element={<PrivateRoute><Profile /></PrivateRoute>} /> {/* New Route */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}