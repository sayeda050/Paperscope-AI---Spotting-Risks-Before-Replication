import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { RefreshCcw } from 'lucide-react';
import { getAdminJobs, retryAdminJob } from "../../api/analysis.api.js";

import "../Dashboard/Dashboard.css";
import './AdminJobs.css';

function formatStatusLabel(status) {
  if (status === "DONE") return "Completed";
  if (status === "FAILED") return "Failed";
  if (status === "PROCESSING") return "Processing";
  if (status === "QUEUED") return "Queued";
  return status || "";
}

export default function AdminJobs() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [retryingJobId, setRetryingJobId] = useState(null);

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
      loadJobs();
    }
  }, [initializing, user]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  async function loadJobs() {
    try {
      const data = await getAdminJobs();
      const normalized = (data?.jobs || []).map((job) => ({
        id: job.job_id,
        paper: job.paper_title || "Untitled Paper",
        user: job.user_name || "Unknown User",
        status: formatStatusLabel(job.status),
        created: job.created_at ? new Date(job.created_at).toLocaleDateString() : "—",
      }));
      setJobs(normalized);
    } catch (error) {
      setJobs([]);
    }
  }

  async function handleRetry(jobId) {
    try {
      setRetryingJobId(jobId);
      await retryAdminJob(jobId);
      await loadJobs();
    } catch (error) {
      alert(
        error?.response?.data?.detail ||
        "Failed to retry the job."
      );
    } finally {
      setRetryingJobId(null);
    }
  }

  const getStatusClass = (status) => {
    switch (status.toLowerCase()) {
      case 'completed': return 'badge-completed';
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
                {jobs.length === 0 ? (
                  <tr className="job-row">
                    <td colSpan="5">No jobs found.</td>
                  </tr>
                ) : (
                  jobs.map((job) => (
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
                          <button
                            className="retry-btn"
                            onClick={() => handleRetry(job.id)}
                            disabled={retryingJobId === job.id}
                          >
                            <RefreshCcw size={14} /> {retryingJobId === job.id ? "Retrying..." : "Retry"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}