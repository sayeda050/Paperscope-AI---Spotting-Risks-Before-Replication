import React, { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx"; // Real auth context
import "./Dashboard.css";


export default function Dashboard() {
  const { user, logout, initializing } = useAuth(); // Get real user data
  const navigate = useNavigate();


  // 1. FIX THE LOOP: Wait for the auth check to finish before redirecting
  useEffect(() => {
    if (!initializing && !user) {
      navigate('/login');
    }
  }, [user, initializing, navigate]);


  // 2. SHOW LOADING: Prevents the "Flash" of the login page
  if (initializing) {
    return (
      <div className="ps-loading-screen">
        <div className="ps-loading-spinner"></div>
        <p>Loading your research workspace...</p>
      </div>
    );
  }


  // Safety check
  if (!user) return null;


  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };


  // Mock data preserved as requested - replace these with API calls later
  const mockPapers = [
    { id: "p1", userId: user.user_id, title: "Deep Learning for Protein Folding: A Reproducibility Study" },
    { id: "p2", userId: user.user_id, title: "Attention Mechanisms in Low-Resource NLP" },
    { id: "p3", userId: user.user_id, title: "Statistical Methods for Climate Model Validation" },
    { id: "p4", userId: user.user_id, title: "Generative Adversarial Networks for Medical Imaging" },
  ];


  const mockJobs = [
    { id: "j1", userId: user.user_id, status: "COMPLETED", paperTitle: mockPapers[0].title, createdAt: "2025-01-10T12:00:00Z", riskLabel: "HIGH", riskScore: 0.72 },
    { id: "j2", userId: user.user_id, status: "COMPLETED", paperTitle: mockPapers[1].title, createdAt: "2025-01-15T12:00:00Z", riskLabel: "LOW", riskScore: 0.34 },
    { id: "j3", userId: user.user_id, status: "FAILED", paperTitle: mockPapers[2].title, createdAt: "2025-01-22T12:00:00Z", riskLabel: null, riskScore: null },
    { id: "j4", userId: user.user_id, status: "QUEUED", paperTitle: mockPapers[3].title, createdAt: "2025-02-10T12:00:00Z", riskLabel: null, riskScore: null },
  ];


  const totalPapers = mockPapers.length;
  const completed = mockJobs.filter((j) => j.status === "COMPLETED").length;
  const inProgress = mockJobs.filter((j) => j.status === "QUEUED" || j.status === "PROCESSING").length;
  const failed = mockJobs.filter((j) => j.status === "FAILED").length;


  const quickActions = [
    { label: "Upload PDF", desc: "Submit a paper for analysis", to: "/dashboard/submit", icon: "⬆️" },
    { label: "Analyze arXiv", desc: "Analyze by arXiv link or ID", to: "/dashboard/submit", icon: "🔎" },
    { label: "View History", desc: "Browse past analyses", to: "/dashboard/history", icon: "🕘" },
  ];


  const navItems = [
    { label: "Dashboard", to: "/dashboard", icon: "▦", active: true },
    { label: "Submit Paper", to: "/dashboard/submit", icon: "⬆" },
    { label: "Analysis Jobs", to: "/dashboard/jobs", icon: "⏱" },
    { label: "History", to: "/dashboard/history", icon: "🕘" },
    { label: "Profile", to: "/dashboard/profile", icon: "👤" },
  ];


  function StatusBadge({ status }) {
    const s = String(status || "").toLowerCase();
    return <span className={`ps-pill ps-status ps-status-${s}`}>{status}</span>;
  }


  function RiskBadge({ label, score }) {
    if (!label) return null;
    const l = String(label).toLowerCase();
    const pct = Math.round((score || 0) * 100);
    const text = `${label} Risk (${pct})`;
    return <span className={`ps-pill ps-risk ps-risk-${l}`}>{text}</span>;
  }


  return (
    <div className="ps-app">
      {/* Sidebar */}
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-brand-badge">🛡️</div>
          <div className="ps-brand-text">
            <div className="ps-brand-title">PaperScope AI</div>
          </div>
        </div>


        <div className="ps-nav-title">NAVIGATION</div>


        <nav className="ps-nav">
          {navItems.map((item) => (
            <Link
              key={item.label}
              to={item.to}
              className={`ps-nav-item ${item.active ? "is-active" : ""}`}
            >
              <span className="ps-nav-icon">{item.icon}</span>
              <span className="ps-nav-label">{item.label}</span>
              <span className="ps-nav-arrow">›</span>
            </Link>
          ))}
        </nav>


        <div className="ps-sidebar-footer">
          <div className="ps-userbox">
            {/* Dynamic Avatar using real user initials */}
            <div className="ps-avatar">
              {user.first_name?.[0]}{user.last_name?.[0]}
            </div>
            <div className="ps-userbox-text">
              <div className="ps-userbox-name">{user.first_name} {user.last_name}</div>
              <div className="ps-userbox-email">{user.email}</div>
            </div>
          </div>


          <button className="ps-signout" type="button" onClick={handleLogout}>
            ⎋ Sign Out
          </button>
        </div>
      </aside>


      <main className="ps-main">
        <div className="ps-topbar">
          <div />
          <div className="ps-role-pill">{user.role}</div>
        </div>


        <div className="ps-content">
          <div className="ps-header">
            <h1 className="ps-title">Welcome back, {user.first_name}!</h1>
            <p className="ps-subtitle">Here's an overview of your research analysis activity.</p>
          </div>


          {/* Stats Section */}
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
                <p className="ps-trend ps-trend-positive">↑ Live data active</p>
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


          {/* Recent Jobs */}
          <div className="ps-card ps-jobs-card">
            <div className="ps-jobs-header">
              <h2 className="ps-jobs-title">Recent Analysis Jobs</h2>
              <Link className="ps-view-all" to="/dashboard/jobs">
                View All
              </Link>
            </div>


            <div className="ps-jobs-list">
              {mockJobs.slice(0, 4).map((job) => (
                <div key={job.id} className="ps-job-row">
                  <div className="ps-job-left">
                    <div className="ps-job-title">{job.paperTitle}</div>
                    <div className="ps-job-date">{new Date(job.createdAt).toLocaleDateString()}</div>
                  </div>


                  <div className="ps-job-right">
                    {job.riskLabel && <RiskBadge label={job.riskLabel} score={job.riskScore} />}
                    <StatusBadge status={job.status} />
                  </div>
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
