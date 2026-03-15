import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getUserDashboard } from "../../api/analysis.api.js";
import "./Dashboard.css";

function mapDashboardStatus(status) {
  if (status === "DONE") return "COMPLETED";
  return String(status || "").toUpperCase();
}

function mapDashboardRiskLabel(label) {
  if (label === "Low") return "LOW";
  if (label === "Med") return "MEDIUM";
  if (label === "High") return "HIGH";
  return label || null;
}

export default function Dashboard() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.is_superuser || user?.role === "ADMIN";

  const [stats, setStats] = useState({
    total_papers: 0,
    completed_jobs: 0,
    in_progress_jobs: 0,
    failed_jobs: 0,
  });
  const [recentJobs, setRecentJobs] = useState([]);

  useEffect(() => {
    if (!initializing) {
      if (!user) {
        navigate("/login");
      } else if (isAdmin) {
        navigate("/dashboard/admin");
      }
    }
  }, [user, initializing, isAdmin, navigate]);

  useEffect(() => {
    if (!initializing && user && !isAdmin) {
      loadDashboard();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initializing, user, isAdmin]);

  if (initializing) {
    return (
      <div className="ps-loading-screen">
        <div className="ps-loading-spinner"></div>
        <p>Loading your research workspace...</p>
      </div>
    );
  }

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  async function loadDashboard() {
    try {
      const data = await getUserDashboard();

      setStats({
        total_papers: Number(data?.stats?.total_papers || 0),
        completed_jobs: Number(data?.stats?.completed_jobs || 0),
        in_progress_jobs: Number(data?.stats?.in_progress_jobs || 0),
        failed_jobs: Number(data?.stats?.failed_jobs || 0),
      });

      const normalizedJobs = (data?.recent_jobs || []).map((job) => ({
        id: job.job_id,
        status: mapDashboardStatus(job.status),
        paperTitle: job.paper_title || "Untitled Paper",
        createdAt: job.created_at,
        riskLabel: mapDashboardRiskLabel(job?.result?.risk_label),
        riskScore:
          job?.result?.risk_score !== undefined && job?.result?.risk_score !== null
            ? Number(job.result.risk_score) / 100
            : null,
      }));

      setRecentJobs(normalizedJobs);
    } catch (error) {
      setStats({
        total_papers: 0,
        completed_jobs: 0,
        in_progress_jobs: 0,
        failed_jobs: 0,
      });
      setRecentJobs([]);
    }
  }

  const totalPapers = stats.total_papers;
  const completed = stats.completed_jobs;
  const inProgress = stats.in_progress_jobs;
  const failed = stats.failed_jobs;

  const quickActions = [
    { label: "Upload PDF", desc: "Submit a paper for analysis", to: "/dashboard/submit", icon: "⬆️" },
    { label: "Analyze arXiv", desc: "Analyze by arXiv link or ID", to: "/dashboard/submit", icon: "🔎" },
    { label: "View History", desc: "Browse past analyses", to: "/dashboard/history", icon: "🕘" },
  ];

  function StatusBadge({ status }) {
    const s = String(status || "").toLowerCase();
    return <span className={`ps-pill ps-status ps-status-${s}`}>{status}</span>;
  }

  function RiskBadge({ label, score }) {
    if (!label) return null;
    const l = String(label || "").toLowerCase();
    const pct = Math.round((score || 0) * 100);
    const text = `${label} Risk (${pct})`;
    return <span className={`ps-pill ps-risk ps-risk-${l}`}>{text}</span>;
  }

  return (
    <div className="ps-app">
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>

        <div className="ps-nav-section">
          <p className="ps-nav-label">NAVIGATION</p>
          <Link to="/dashboard" className="ps-nav-link active">
            ▦ Dashboard <span className="ps-chevron">›</span>
          </Link>
          <Link to="/dashboard/submit" className="ps-nav-link">⬆ Submit Paper</Link>
          <Link to="/dashboard/jobs" className="ps-nav-link">⏱ Analysis Jobs</Link>
          <Link to="/dashboard/history" className="ps-nav-link">🕘 History</Link>
          <Link to="/dashboard/profile" className="ps-nav-link">👤 Profile</Link>
        </div>

        <div className="ps-sidebar-footer">
          <div className="ps-user-card">
            <div className="ps-user-avatar">
              {user.first_name?.[0] || ""}
              {user.last_name?.[0] || ""}
            </div>
            <div className="ps-user-meta">
              <p className="ps-user-name">{user.first_name} {user.last_name}</p>
              <p className="ps-user-email">{user.email}</p>
            </div>
          </div>
          <button className="ps-btn-logout" onClick={handleLogout}>
            ⎋ Sign Out
          </button>
        </div>
      </aside>

      <main className="ps-main">
        <div className="ps-topbar">
          <div />
          <div className="ps-role-pill">{isAdmin ? "Admin" : "Researcher"}</div>
        </div>

        <div className="ps-content">
          <div className="ps-header">
            <h1 className="ps-title">Welcome back, {user.first_name}!</h1>
            <p className="ps-subtitle">Here's an overview of your research analysis activity.</p>
          </div>

          <div className="ps-stats-grid">
            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">Total Papers</p>
                <p className="ps-stat-value">{totalPapers}</p>
              </div>
              <div className="ps-stat-icon">📄</div>
            </div>

            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">Completed</p>
                <p className="ps-stat-value">{completed}</p>
                <p className="ps-trend ps-trend-positive">Live system data</p>
              </div>
              <div className="ps-stat-icon">✅</div>
            </div>

            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">In Progress</p>
                <p className="ps-stat-value">{inProgress}</p>
              </div>
              <div className="ps-stat-icon">⏱</div>
            </div>

            <div className="ps-card ps-stat-card">
              <div>
                <p className="ps-stat-title">Failed</p>
                <p className="ps-stat-value">{failed}</p>
              </div>
              <div className="ps-stat-icon">⚠️</div>
            </div>
          </div>

          <div className="ps-actions-grid">
            {quickActions.map((a) => (
              <Link key={a.label} to={a.to} className="ps-card ps-action-card">
                <div className="ps-action-inner">
                  <div className="ps-action-icon">{a.icon}</div>
                  <div>
                    <div className="ps-action-label">{a.label}</div>
                    <div className="ps-action-desc">{a.desc}</div>
                  </div>
                </div>
              </Link>
            ))}
          </div>

          <div className="ps-card ps-jobs-card">
            <div className="ps-jobs-header">
              <h2 className="ps-jobs-title">Recent Analysis Jobs</h2>
              <Link className="ps-view-all" to="/dashboard/jobs">
                View All
              </Link>
            </div>

            <div className="ps-jobs-list">
              {recentJobs.length === 0 ? (
                <div className="ps-job-row">
                  <div className="ps-job-left">
                    <div className="ps-job-title">No analysis jobs yet.</div>
                    <div className="ps-job-date">Submit a paper to get started.</div>
                  </div>
                </div>
              ) : (
                recentJobs.slice(0, 4).map((job) => (
                  <div key={job.id} className="ps-job-row">
                    <div className="ps-job-left">
                      <div className="ps-job-title">{job.paperTitle}</div>
                      <div className="ps-job-date">
                        {job.createdAt ? new Date(job.createdAt).toLocaleDateString() : "—"}
                      </div>
                    </div>

                    <div className="ps-job-right">
                      {job.riskLabel && <RiskBadge label={job.riskLabel} score={job.riskScore} />}
                      <StatusBadge status={job.status} />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div style={{ height: 18 }} />
        </div>
      </main>
    </div>
  );
}