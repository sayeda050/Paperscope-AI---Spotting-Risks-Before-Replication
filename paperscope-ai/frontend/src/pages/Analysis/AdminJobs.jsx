import React, { useState } from 'react';
import { 
  Shield, 
  LayoutDashboard, 
  Users, 
  FileText, 
  Clock, 
  CheckSquare, 
  Box, 
  AlertTriangle, 
  User, 
  LogOut,
  RefreshCcw,
  ChevronDown
} from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import './AdminJobs.css';

export default function AdminJobs() {
  const { user, logout } = useAuth(); // Fetches real-time user data [cite: 191, 192, 194]
  const navigate = useNavigate();
  
  // Real-time derived user display data
  const displayName = user?.full_name || 
                      (user?.first_name && user?.last_name ? `${user.first_name} ${user.last_name}` : null) || 
                      user?.email?.split('@')[0] || 
                      'User';

  const displayEmail = user?.email || 'admin@paperscope.ai';

  // Derived initials for the avatar (e.g., "Sarah Chen" -> "SC", "anindita.lubaba" -> "AL")
  const getInitials = (name, email) => {
    if (name && name !== 'User') {
      const parts = name.split(/[\s._]/);
      return parts.map(n => n[0]).join('').toUpperCase().substring(0, 2);
    }
    if (email) return email[0].toUpperCase();
    return "U";
  };

  const handleSignOut = async () => {
    await logout();
    navigate('/login');
  };

  // Mock data for analysis jobs matching project lifecycle [cite: 242]
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

  return (
    <div className="admin-page-layout">
      {/* --- SIDEBAR PANEL --- */}
      <aside className="admin-sidebar">
        <div className="sidebar-brand">
          <Shield className="brand-icon" />
          <span>PaperScope AI</span>
        </div>

        <div className="sidebar-section">
          <p className="section-label">ADMINISTRATION</p>
          <nav className="sidebar-nav">
            <Link to="/dashboard/admin" className="nav-item">
              <LayoutDashboard size={18} /> DASHBOARD
            </Link>
            <Link to="/dashboard/admin/users" className="nav-item">
              <Users size={18} /> USERS
            </Link>
            <Link to="/dashboard/admin/papers" className="nav-item">
              <FileText size={18} /> PAPERS
            </Link>
            <Link to="/dashboard/admin/jobs" className="nav-item active">
              <Clock size={18} /> JOBS
              <div className="active-indicator" />
            </Link>
            <Link to="#" className="nav-item">
              <CheckSquare size={18} /> RESULTS
            </Link>
            <Link to="#" className="nav-item">
              <Box size={18} /> MODELS
            </Link>
            <Link to="#" className="nav-item">
              <AlertTriangle size={18} /> ERROR LOGS
            </Link>
            <Link to="/dashboard/profile" className="nav-item">
              <User size={18} /> PROFILE
            </Link>
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="user-profile-card">
            <div className="user-avatar">
              {getInitials(displayName, displayEmail)}
            </div>
            <div className="user-info">
              <p className="user-name">{displayName}</p>
              <p className="user-email">{displayEmail}</p>
            </div>
          </div>
          <button className="sign-out-btn" onClick={handleSignOut}>
            <LogOut size={18} /> Sign Out
          </button>
        </div>
      </aside>

      {/* --- MAIN CONTENT AREA --- */}
      <main className="admin-main-content">
        <header className="main-header">
          <div className="header-badge">Admin</div>
        </header>

        <div className="content-container">
          <div className="content-title-row">
            <div>
              <h1 className="content-title">Manage Jobs</h1>
              <p className="content-subtitle">Monitor and manage all analysis jobs.</p>
            </div>
            
            <div className="filter-dropdown">
              <select className="filter-select">
                <option value="all">All</option>
                <option value="completed">Completed</option>
              </select>
              <ChevronDown className="filter-chevron" size={16} />
            </div>
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
                    <td className="user-name-cell">{job.user}</td>
                    <td>
                      <span className={`status-badge ${getStatusClass(job.status)}`}>
                        {job.status}
                      </span>
                    </td>
                    <td className="date-cell">{job.created}</td>
                    <td className="actions-cell">
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