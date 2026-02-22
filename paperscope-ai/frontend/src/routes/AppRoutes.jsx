import { Navigate, Route, Routes } from "react-router-dom";

import Index from "../pages/Auth/Index.jsx";         // <-- adjust if your Index file is elsewhere
import Login from "../pages/Auth/Login.jsx";
import Register from "../pages/Auth/Register.jsx";
import Dashboard from "../pages/Dashboard/Dashboard.jsx";

import { useAuth } from "../contexts/AuthContext.jsx";

function PrivateRoute({ children }) {
  const { isAuthed, initializing } = useAuth();
  if (initializing) return null;
  return isAuthed ? children : <Navigate to="/login" replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      {/* ✅ LANDING PAGE AS HOMEPAGE */}
      <Route path="/" element={<Index />} />

      {/* Auth pages */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* ✅ Protected dashboard */}
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <Dashboard />
          </PrivateRoute>
        }
      />

      {/* fallback */}
      <Route path="*" element={<div style={{ padding: 40, fontSize: 20 }}>404 Not Found</div>} />
    </Routes>
  );
}