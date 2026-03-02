import React, { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx"; 
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell } from "recharts";

import "./Dashboard.css"; // Ensures the Sidebar styling matches exactly
import "./AdminDashboard.css";

export default function AdminDashboard() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();

  // Restricts regular users from accessing this page
  useEffect(() => {
    if (!initializing) {
      if (!user) {
        navigate('/login');
      } else if (!user.is_superuser && user.role !== 'ADMIN') {
        navigate('/dashboard');
      }
    }
  }, [user, initializing, navigate]);

  if (initializing) {
    return (
      <div className="ps-loading-screen">
        <div className="ps-loading-spinner"></div>
        <p>Verifying admin session...</p>
      </div>
    );
  }

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // --- UNTOUCHED MOCK DATA ---
  const mockUsers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]; 
  const mockPapers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]; 
  const mockErrorLogs = [1, 2, 3]; 

  const mockJobs = [
    { id: "j1", status: "DONE" }, { id: "j2", status: "DONE" }, { id: "j3", status: "DONE" },
    { id: "j4", status: "DONE" }, { id: "j5", status: "DONE" }, { id: "j6", status: "PROCESSING" },
    { id: "j7", status: "PROCESSING" }, { id: "j8", status: "QUEUED" }, { id: "j9", status: "FAILED" }
  ];

  const jobsByDay = [
    { day: 'Mon', count: 3 }, { day: 'Tue', count: 5 }, { day: 'Wed', count: 2 },
    { day: 'Thu', count: 7 }, { day: 'Fri', count: 4 }, { day: 'Sat', count: 1 }, { day: 'Sun', count: 2 },
  ];

  const riskDist = [
    { name: 'Low', value: 12, color: 'hsl(142, 76%, 36%)' },
    { name: 'Medium', value: 8, color: 'hsl(38, 92%, 50%)' },
    { name: 'High', value: 5, color: 'hsl(0, 72%, 51%)' },
  ];

  const completedJobs = mockJobs.filter(j => j.status === 'DONE').length;
  
  const statusDist = [
    { name: 'Done', value: completedJobs, colorClass: 'ps-text-done', icon: '✅' },
    { name: 'Processing', value: mockJobs.filter(j => j.status === 'PROCESSING').length, colorClass: 'ps-text-processing', icon: '🔄' },
    { name: 'Queued', value: mockJobs.filter(j => j.status === 'QUEUED').length, colorClass: 'ps-text-queued', icon: '⏳' },
    { name: 'Failed', value: mockJobs.filter(j => j.status === 'FAILED').length, colorClass: 'ps-text-failed', icon: '❌' },
  ];

  return (
    <div className="ps-app">
      {/* SIDEBAR - UPDATED TO EXACT ADMIN MENU */}
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>
        <div className="ps-nav-section">
          <p className="ps-nav-label">ADMINISTRATION</p>
          <Link to="/dashboard/admin" className="ps-nav-link active">▦ Dashboard <span className="ps-chevron">›</span></Link>
          <Link to="/dashboard/admin/users" className="ps-nav-link">👥 Users</Link>
          <Link to="/dashboard/admin/papers" className="ps-nav-link">📄 Papers</Link>
          <Link to="/dashboard/admin/jobs" className="ps-nav-link">⏱ Jobs</Link>
          <Link to="/dashboard/admin/results" className="ps-nav-link">🗄️ Results</Link>
          <Link to="/dashboard/admin/models" className="ps-nav-link">💠 Models</Link>
          <Link to="/dashboard/admin/errors" className="ps-nav-link">⚠️ Error Logs</Link>
          <Link to="/dashboard/profile" className="ps-nav-link">👤 Profile</Link>
        </div>
        <div className="ps-sidebar-footer">
          <div className="ps-user-card">
            <div className="ps-user-avatar">
              {user.first_name?.[0] || ""}{user.last_name?.[0] || ""}
            </div>
            <div className="ps-user-meta">
              <p className="ps-user-name">{user.first_name} {user.last_name}</p>
              <p className="ps-user-email">{user.email}</p>
            </div>
          </div>
          <button className="ps-btn-logout" onClick={handleLogout}>⎋ Sign Out</button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA - STRICTLY UNTOUCHED */}
      <main className="ps-main">
        <div className="ps-topbar">
          <div />
          <div className="ps-role-pill ps-role-admin">Administrator</div>
        </div>

        <div className="ps-content">
          <div className="ps-header">
            <h1 className="ps-title">Admin Dashboard</h1>
            <p className="ps-subtitle">System-wide overview and monitoring.</p>
          </div>

          <div className="ps-stats-grid">
            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">Total Users</p>
                <p className="ps-stat-value">{mockUsers.length}</p>
                <p className="ps-trend ps-trend-positive">↑ +3 this month</p>
              </div>
              <div className="ps-stat-icon">👥</div>
            </div>

            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">Total Papers</p>
                <p className="ps-stat-value">{mockPapers.length}</p>
              </div>
              <div className="ps-stat-icon">📄</div>
            </div>

            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">Completed Jobs</p>
                <p className="ps-stat-value">{completedJobs}</p>
              </div>
              <div className="ps-stat-icon">✅</div>
            </div>

            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">Errors</p>
                <p className="ps-stat-value">{mockErrorLogs.length}</p>
              </div>
              <div className="ps-stat-icon ps-icon-error">⚠️</div>
            </div>
          </div>

          <div className="ps-charts-grid">
            <div className="ps-card ps-chart-card card-shine">
              <div className="ps-chart-header">Jobs Over Time</div>
              <div className="ps-chart-body">
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={jobsByDay}>
                    <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                    <Bar dataKey="count" fill="hsl(172, 66%, 30%)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="ps-card ps-chart-card card-shine">
              <div className="ps-chart-header">Risk Label Distribution</div>
              <div className="ps-chart-body" style={{ display: 'flex', justifyContent: 'center' }}>
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie data={riskDist} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                      {riskDist.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                    </Pie>
                    <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="ps-card card-shine">
            <div className="ps-chart-header" style={{ padding: '16px 16px 0 16px' }}>Job Status Summary</div>
            <div className="ps-status-summary-grid">
              {statusDist.map(s => (
                <div key={s.name} className="ps-status-box">
                  <div className="ps-status-icon">{s.icon}</div>
                  <p className={`ps-status-val ${s.colorClass}`}>{s.value}</p>
                  <p className="ps-status-name">{s.name}</p>
                </div>
              ))}
            </div>
          </div>
          <div style={{ height: 18 }} />
        </div>
      </main>
    </div>
  );
}