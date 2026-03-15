import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell } from "recharts";
import { getAdminDashboard } from "../../api/analysis.api.js";

import "./Dashboard.css";
import "./AdminDashboard.css";

function formatChartDay(dayValue) {
  if (!dayValue) return "";
  const d = new Date(dayValue);
  if (Number.isNaN(d.getTime())) return String(dayValue);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function AdminDashboard() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();

  const [stats, setStats] = useState({
    total_users: 0,
    total_papers: 0,
    completed_jobs: 0,
    error_logs: 0,
  });
  const [jobsByDay, setJobsByDay] = useState([]);
  const [riskDist, setRiskDist] = useState([
    { name: 'Low', value: 0, color: 'hsl(142, 76%, 36%)' },
    { name: 'Medium', value: 0, color: 'hsl(38, 92%, 50%)' },
    { name: 'High', value: 0, color: 'hsl(0, 72%, 51%)' },
  ]);
  const [statusDist, setStatusDist] = useState([
    { name: 'Done', value: 0, colorClass: 'ps-text-done', icon: '✅' },
    { name: 'Processing', value: 0, colorClass: 'ps-text-processing', icon: '🔄' },
    { name: 'Queued', value: 0, colorClass: 'ps-text-queued', icon: '⏳' },
    { name: 'Failed', value: 0, colorClass: 'ps-text-failed', icon: '❌' },
  ]);

  useEffect(() => {
    if (!initializing) {
      if (!user) {
        navigate('/login');
      } else if (!user.is_superuser && user.role !== 'ADMIN') {
        navigate('/dashboard');
      }
    }
  }, [user, initializing, navigate]);

  useEffect(() => {
    if (!initializing && user && (user.is_superuser || user.role === "ADMIN")) {
      loadAdminDashboard();
    }
  }, [initializing, user]);

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

  async function loadAdminDashboard() {
    try {
      const data = await getAdminDashboard();

      setStats({
        total_users: Number(data?.stats?.total_users || 0),
        total_papers: Number(data?.stats?.total_papers || 0),
        completed_jobs: Number(data?.stats?.completed_jobs || 0),
        error_logs: Number(data?.stats?.error_logs || 0),
      });

      setJobsByDay(
        (data?.jobs_by_day || []).map((row) => ({
          day: formatChartDay(row.day),
          count: Number(row.count || 0),
        }))
      );

      setRiskDist([
        {
          name: 'Low',
          value: Number((data?.risk_distribution || []).find((r) => r.name === "Low")?.value || 0),
          color: 'hsl(142, 76%, 36%)',
        },
        {
          name: 'Medium',
          value: Number((data?.risk_distribution || []).find((r) => r.name === "Medium")?.value || 0),
          color: 'hsl(38, 92%, 50%)',
        },
        {
          name: 'High',
          value: Number((data?.risk_distribution || []).find((r) => r.name === "High")?.value || 0),
          color: 'hsl(0, 72%, 51%)',
        },
      ]);

      const rawStatus = data?.status_distribution || [];
      setStatusDist([
        { name: 'Done', value: Number(rawStatus.find((s) => s.name === 'Done')?.value || 0), colorClass: 'ps-text-done', icon: '✅' },
        { name: 'Processing', value: Number(rawStatus.find((s) => s.name === 'Processing')?.value || 0), colorClass: 'ps-text-processing', icon: '🔄' },
        { name: 'Queued', value: Number(rawStatus.find((s) => s.name === 'Queued')?.value || 0), colorClass: 'ps-text-queued', icon: '⏳' },
        { name: 'Failed', value: Number(rawStatus.find((s) => s.name === 'Failed')?.value || 0), colorClass: 'ps-text-failed', icon: '❌' },
      ]);
    } catch (error) {
      setStats({
        total_users: 0,
        total_papers: 0,
        completed_jobs: 0,
        error_logs: 0,
      });
      setJobsByDay([]);
      setRiskDist([
        { name: 'Low', value: 0, color: 'hsl(142, 76%, 36%)' },
        { name: 'Medium', value: 0, color: 'hsl(38, 92%, 50%)' },
        { name: 'High', value: 0, color: 'hsl(0, 72%, 51%)' },
      ]);
      setStatusDist([
        { name: 'Done', value: 0, colorClass: 'ps-text-done', icon: '✅' },
        { name: 'Processing', value: 0, colorClass: 'ps-text-processing', icon: '🔄' },
        { name: 'Queued', value: 0, colorClass: 'ps-text-queued', icon: '⏳' },
        { name: 'Failed', value: 0, colorClass: 'ps-text-failed', icon: '❌' },
      ]);
    }
  }

  const completedJobs = stats.completed_jobs;

  return (
    <div className="ps-app">
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
                <p className="ps-stat-value">{stats.total_users}</p>
                <p className="ps-trend ps-trend-positive">Live system data</p>
              </div>
              <div className="ps-stat-icon">👥</div>
            </div>

            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">Total Papers</p>
                <p className="ps-stat-value">{stats.total_papers}</p>
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
                <p className="ps-stat-value">{stats.error_logs}</p>
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