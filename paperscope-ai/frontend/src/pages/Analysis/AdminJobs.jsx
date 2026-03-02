import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { RefreshCcw, ChevronDown } from 'lucide-react';

import "../Dashboard/Dashboard.css"; // Ensure this path points to your main dashboard CSS
import './AdminJobs.css';

export default function AdminJobs() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Mock data for analysis jobs
  const [jobs] = useState([
    { id: 1, paper: "Deep Learning for Protein Folding: A Reproducibility Study", user: "Alex Rivera", status: "Completed", created: "1/10/2025" },
    { id: 2, paper: "Attention Mechanisms in Low-Resource NLP", user: "Alex Rivera", status: "Completed", created: "1/15/2025" },
    { id: 3, paper: "Statistical Methods for Climate Model Validation", user: "Alex Rivera", status: "Failed", created: "1/22/2025" },
    { id: 4, paper: "Quantum Error Correction with Topological Codes", user: "Jane Park", status: "Processing", created: "2/1/2025" },
    { id: 5, paper: "Generative Adversarial Networks for Medical Imaging", user: "Alex Rivera", status: "Queued", created: "2/10/2025" },
    { id: 6, paper: "Reinforcement Learning in Autonomous Navigation", user: "Mike Thompson", status: "Completed", created: "2/14/2025" },
  ]);

  const getStatusClass = (status) => {
    switch (status.toLowerCase()) {
      case 'completed': case 'done': return 'badge-completed';
      case 'failed': return 'badge-failed';
      case 'processing': return 'badge-processing';
      case 'queued': return 'badge-queued';
      default: return '';
    }
  };

  if (initializing) return null;
  if (!user) return null;

  return (
    <div className="ps-app">
      {/* SIDEBAR - EXACT MATCH TO ADMIN DASHBOARD */}
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>
        <div className="ps-nav-section">
          <p className="ps-nav-label">ADMINISTRATION</p>
          <Link to="/dashboard/admin" className="ps-nav-link">▦ Dashboard</Link>
          <Link to="/dashboard/admin/users" className="ps-nav-link">👥 Users</Link>
          <Link to="/dashboard/admin/papers" className="ps-nav-link">📄 Papers</Link>
          <Link to="/dashboard/admin/jobs" className="ps-nav-link active">⏱ Jobs <span className="ps-chevron">›</span></Link>
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

      {/* MAIN CONTENT AREA */}
      <main className="ps-main">
        <div className="ps-topbar">
          <div />
          <div className="ps-role-pill ps-role-admin">Administrator</div>
        </div>

        <div className="ps-content">
          <div className="ps-header">
            <h1 className="ps-title">Manage Jobs</h1>
            <p className="ps-subtitle">Monitor and manage all system analysis jobs.</p>
          </div>

          <div className="table-card">
            <table className="jobs-table">
              <thead>
                <tr>
                  <th>Paper</th>
                  <th>User</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} className="job-row">
                    <td className="paper-name">{job.paper}</td>
                    <td>{job.user}</td>
                    <td>
                      <span className={`status-badge ${getStatusClass(job.status)}`}>
                        {job.status}
                      </span>
                    </td>
                    <td>{job.created}</td>
                    <td className="text-right">
                      {job.status === 'Failed' && (
                        <button className="retry-btn">
                          <RefreshCcw size={14} /> Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}