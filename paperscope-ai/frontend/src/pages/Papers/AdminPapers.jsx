import React, { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";

import "../Dashboard/Dashboard.css";
import './AdminPapers.css';

const mockPapers = [
  { id: 1, title: 'Deep Learning for Protein Folding: A Repro...', submitter: 'Alex Rivera', source: 'PDF', uploaded: '1/10/2025' },
  { id: 2, title: 'Attention Mechanisms in Low-Resource NLP', submitter: 'Alex Rivera', source: 'arXiv', uploaded: '1/15/2025' },
  { id: 3, title: 'Statistical Methods for Climate Model Valid...', submitter: 'Alex Rivera', source: 'PDF', uploaded: '1/22/2025' },
  { id: 4, title: 'Quantum Error Correction with Topological ...', submitter: 'Jane Park', source: 'arXiv', uploaded: '2/1/2025' },
  { id: 5, title: 'Generative Adversarial Networks for Medic...', submitter: 'Alex Rivera', source: 'PDF', uploaded: '2/10/2025' },
  { id: 6, title: 'Reinforcement Learning in Autonomous Na...', submitter: 'Mike Thompson', source: 'arXiv', uploaded: '2/14/2025' },
];

export default function AdminPapers() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!initializing) {
      if (!user) {
        navigate('/login');
      } else if (!user.is_superuser && user.role !== 'ADMIN') {
        navigate('/dashboard');
      }
    }
  }, [user, initializing, navigate]);

  if (initializing) return null;
  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

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
          <Link to="/dashboard/admin/papers" className="ps-nav-link active">📄 Papers <span className="ps-chevron">›</span></Link>
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

      {/* MAIN CONTENT AREA */}
      <main className="ps-main">
        <div className="ps-topbar">
          <div />
          <div className="ps-role-pill ps-role-admin">Administrator</div>
        </div>

        <div className="ps-content">
          <div className="ps-header">
            <h1 className="ps-title">Manage Papers</h1>
            <p className="ps-subtitle">All submitted research papers across the platform.</p>
          </div>

          <div className="table-card">
            <table className="jobs-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Submitter</th>
                  <th>Source</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {mockPapers.map((paper) => (
                  <tr key={paper.id} className="job-row">
                    <td className="paper-name">{paper.title}</td>
                    <td>{paper.submitter}</td>
                    <td>
                      <span className="ps-pill ps-status-queued">{paper.source}</span>
                    </td>
                    <td>{paper.uploaded}</td>
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