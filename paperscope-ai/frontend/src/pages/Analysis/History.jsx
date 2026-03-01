import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import "./History.css";

// Icons
const SearchIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>;
const EyeIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>;
const FilterIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>;

export default function History() {
  const { user, logout } = useAuth();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [riskFilter, setRiskFilter] = useState('all');

  if (!user) return null;

  // Mock data integrated directly as per your previous logic
  const mockJobs = [
    { id: "j1", userId: "2", status: "DONE", paperTitle: "Deep Learning for Protein Folding: A Reproducibility Study", createdAt: "2025-01-10T12:00:00Z" },
    { id: "j2", userId: "2", status: "DONE", paperTitle: "Attention Mechanisms in Low-Resource NLP", createdAt: "2025-01-15T12:00:00Z" },
    { id: "j3", userId: "2", status: "FAILED", paperTitle: "Statistical Methods for Climate Model Validation", createdAt: "2025-01-22T12:00:00Z" },
    { id: "j4", userId: "2", status: "QUEUED", paperTitle: "Generative Adversarial Networks for Medical Imaging", createdAt: "2025-02-10T12:00:00Z" },
  ];

  const mockResults = [
    { jobId: 'j1', riskScore: 72, riskLabel: 'High' },
    { jobId: 'j2', riskScore: 24, riskLabel: 'Low' },
  ];

  const filtered = mockJobs.filter(j => j.userId === '2').filter(j => {
    if (search && !j.paperTitle?.toLowerCase().includes(search.toLowerCase())) return false;
    if (statusFilter !== 'all' && j.status !== statusFilter) return false;
    if (riskFilter !== 'all') {
      const result = mockResults.find(r => r.jobId === j.id);
      if (!result || result.riskLabel !== riskFilter) return false;
    }
    return true;
  });

  return (
    <div className="ps-dashboard-layout">
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>
        <div className="ps-nav-section">
          <p className="ps-nav-label">NAVIGATION</p>
          <Link to="/dashboard" className="ps-nav-link">▦ Dashboard</Link>
          <Link to="/dashboard/submit" className="ps-nav-link">⬆ Submit Paper</Link>
          <Link to="/dashboard/jobs" className="ps-nav-link">⏱ Analysis Jobs</Link>
          <Link to="/dashboard/history" className="ps-nav-link active">🕘 History <span className="ps-chevron">›</span></Link>
          <Link to="/dashboard/profile" className="ps-nav-link">👤 Profile</Link>
        </div>
        <div className="ps-sidebar-footer">
          <div className="ps-user-card">
            <div className="ps-user-avatar">{user.first_name?.[0]}{user.last_name?.[0]}</div>
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
              <h1 className="ps-view-title">Analysis History</h1>
              <p className="ps-view-subtitle">Browse and filter your past paper analyses.</p>
            </div>
          </div>

          <div className="ps-filter-bar">
            <div className="ps-search-wrapper">
              <div className="ps-search-icon"><SearchIcon /></div>
              <input 
                type="text" 
                placeholder="Search by title..." 
                className="ps-input" 
                value={search} 
                onChange={e => setSearch(e.target.value)} 
              />
            </div>
            <select className="ps-select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="all">All Status</option>
              <option value="DONE">Completed</option>
              <option value="QUEUED">Queued</option>
              <option value="FAILED">Failed</option>
            </select>
            <select className="ps-select" value={riskFilter} onChange={e => setRiskFilter(e.target.value)}>
              <option value="all">All Risk</option>
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
            </select>
          </div>

          <div className="ps-history-list">
            {filtered.length === 0 ? (
              <div className="ps-empty-state">
                <p>No results match your filters.</p>
              </div>
            ) : (
              filtered.map(job => {
                const result = mockResults.find(r => r.jobId === job.id);
                return (
                  <div key={job.id} className="ps-history-card">
                    <div className="ps-history-info">
                      <p className="ps-history-title">{job.paperTitle}</p>
                      <p className="ps-history-date">{new Date(job.createdAt).toLocaleDateString()}</p>
                    </div>
                    <div className="ps-history-actions">
                      {result && (
                        <span className={`ps-risk-tag ps-risk-${result.riskLabel.toLowerCase()}`}>
                          {result.riskLabel} Risk ({result.riskScore})
                        </span>
                      )}
                      <span className={`ps-status-tag ps-status-${job.status.toLowerCase()}`}>
                        {job.status}
                      </span>
                      {job.status === 'DONE' && (
                        <Link to={`/dashboard/result/${job.id}`} className="ps-icon-btn">
                          <EyeIcon />
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </main>
    </div>
  );
}