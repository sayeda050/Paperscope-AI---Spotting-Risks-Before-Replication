import React from 'react';
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";

// Import your exact page structure
import Index from "../pages/Auth/Index.jsx";
import Login from "../pages/Auth/Login.jsx";
import Register from "../pages/Auth/Register.jsx";
import Dashboard from "../pages/Dashboard/Dashboard.jsx";
import AdminDashboard from "../pages/Dashboard/AdminDashboard.jsx"; // <-- Added Admin Import
import AdminPapers from "../pages/Papers/AdminPapers.jsx"; // <-- NEW: Added AdminPapers Import
import AdminUsers from "../pages/Dashboard/AdminUsers.jsx"; // <-- NEW: Added AdminUsers Import
import AdminJobs from "../pages/Analysis/AdminJobs.jsx"; // <-- NEW: Added AdminJobs Import
import AnalysisJobs from "../pages/Analysis/AnalysisJobs.jsx";
import AnalysisResult from "../pages/Analysis/AnalysisResult.jsx";
import History from "../pages/Analysis/History.jsx"; 
import Profile from "../pages/Dashboard/Profile.jsx"; 

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
      
      {/* <-- Added Admin Route Here --> */}
      <Route path="/dashboard/admin" element={<PrivateRoute><AdminDashboard /></PrivateRoute>} />
      
      {/* <-- NEW: Added Admin Papers Route Here --> */}
      <Route path="/dashboard/admin/papers" element={<PrivateRoute><AdminPapers /></PrivateRoute>} />

      {/* <-- NEW: Added Admin Users Route Here --> */}
      <Route path="/dashboard/admin/users" element={<PrivateRoute><AdminUsers /></PrivateRoute>} />
      
      {/* <-- NEW: Added Admin Jobs Route Here --> */}
      <Route path="/dashboard/admin/jobs" element={<PrivateRoute><AdminJobs /></PrivateRoute>} />
      
      <Route path="/dashboard/jobs" element={<PrivateRoute><AnalysisJobs /></PrivateRoute>} />
      <Route path="/dashboard/history" element={<PrivateRoute><History /></PrivateRoute>} /> 
      <Route path="/dashboard/result/:jobId" element={<PrivateRoute><AnalysisResult /></PrivateRoute>} />
      <Route path="/dashboard/profile" element={<PrivateRoute><Profile /></PrivateRoute>} /> 
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}