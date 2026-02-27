import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import "./AnalysisJobs.css";

// Lucide Icons (Mocking the imports for consistency with your snippet)
const RefreshCw = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></svg>;
const EyeIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>;

export default function AnalysisJobs() {
  const { user, logout } = useAuth(); // Destructured logout here

  // Safety check to prevent crashes if user is still loading
  if (!user) return null;

  // Your exact mock data logic
  const mockJobs = [
    { id: "j1", userId: "2", status: "DONE", paperTitle: "Deep Learning for Protein Folding: A Reproducibility Study", createdAt: "2025-01-10T12:00:00Z", errorMessage: null },
    { id: "j2", userId: "2", status: "DONE", paperTitle: "Attention Mechanisms in Low-Resource NLP", createdAt: "2025-01-15T12:00:00Z", errorMessage: null },
    { id: "j3", userId: "2", status: "FAILED", paperTitle: "Statistical Methods for Climate Model Validation", createdAt: "2025-01-22T12:00:00Z", errorMessage: "PDF extraction failed: corrupted structure" },
    { id: "j4", userId: "2", status: "QUEUED", paperTitle: "Generative Adversarial Networks for Medical Imaging", createdAt: "2025-02-10T12:00:00Z", errorMessage: null },
  ];

  // Logic: Filter for user '2' as per your code
  const userJobs = mockJobs.filter(j => j.userId === '2');

  function StatusBadge({ status }) {
    const s = String(status).toLowerCase();
    return <span className={`ps-badge ps-badge-${s}`}>{status}</span>;
  }

  return (
    <div className="ps-dashboard-layout">
      {/* Sidebar - Matching your screenshot exactly */}
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>
        <div className="ps-nav-section">
          <p className="ps-nav-label">NAVIGATION</p>
          <Link to="/dashboard" className="ps-nav-link">▦ Dashboard</Link>
          <Link to="/dashboard/submit" className="ps-nav-link">⬆ Submit Paper</Link>
          <Link to="/dashboard/jobs" className="ps-nav-link active">⏱ Analysis Jobs <span className="ps-chevron">›</span></Link>
          <Link to="/dashboard/history" className="ps-nav-link">🕘 History</Link>
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
          <button className="ps-btn-logout" onClick={logout}>⎋ Sign Out</button>
        </div>
      </aside>

      <main className="ps-main-content">
        <header className="ps-top-bar">
          <div />
          <span className="ps-role-badge">Researcher</span>
        </header>

        <div className="ps-page-container">
          <div className="ps-page-header">
            <div>
              <h1 className="ps-view-title">Analysis Jobs</h1>
              <p className="ps-view-subtitle">Track the status of your analysis jobs.</p>
            </div>
            <button className="ps-btn-outline">
              <RefreshCw /> Refresh
            </button>
          </div>

          <div className="ps-card shadow-sm">
            <div className="ps-table-scroll">
              <table className="ps-table">
                <thead>
                  <tr>
                    <th>Paper</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Error</th>
                    <th className="text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {userJobs.map(job => (
                    <tr key={job.id} className="ps-table-row">
                      <td className="ps-td-main">{job.paperTitle}</td>
                      <td><StatusBadge status={job.status} /></td>
                      <td className="ps-td-muted">{new Date(job.createdAt).toLocaleDateString()}</td>
                      <td className="ps-td-muted truncate">{job.errorMessage || '—'}</td>
                      <td className="text-right">
                        {job.status === 'DONE' && (
                          <Link to={`/dashboard/result/${job.id}`} className="ps-btn-ghost">
                            <EyeIcon /> View
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}