import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import "./Profile.css";

// SVG Icons matching your dashboard UI
const UserIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
const LockIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>;
const Loader2 = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="ps-profile-spinner"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>;

export default function Profile() {
  const { user, logout, updateProfile } = useAuth();
  
  // Identify if the logged-in user is an Admin
  const isAdmin = user?.is_superuser || user?.role === 'ADMIN';
  
  // Logic to fetch info from logged-in user
  const [firstName, setFirstName] = useState(user?.first_name || '');
  const [lastName, setLastName] = useState(user?.last_name || '');
  const [saving, setSaving] = useState(false);

  // Re-sync if user object loads asynchronously
  useEffect(() => {
    if (user) {
      setFirstName(user.first_name || '');
      setLastName(user.last_name || '');
    }
  }, [user]);

  if (!user) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    await new Promise(r => setTimeout(r, 800));
    if (updateProfile) {
      updateProfile({ first_name: firstName, last_name: lastName });
    }
    setSaving(false);
    alert('Profile updated successfully!');
  };

  return (
    <div className="ps-dashboard-layout">
      {/* DYNAMIC SIDEBAR: Changes based on isAdmin */}
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>
        
        <div className="ps-nav-section">
          <p className="ps-nav-label">{isAdmin ? "ADMINISTRATION" : "NAVIGATION"}</p>
          
          {isAdmin ? (
            <>
              <Link to="/dashboard/admin" className="ps-nav-link">▦ Dashboard</Link>
              <Link to="/dashboard/admin/users" className="ps-nav-link">👥 Users</Link>
              <Link to="/dashboard/admin/papers" className="ps-nav-link">📄 Papers</Link>
              <Link to="/dashboard/admin/jobs" className="ps-nav-link">⏱ Jobs</Link>
              <Link to="/dashboard/admin/results" className="ps-nav-link">🗄️ Results</Link>
              <Link to="/dashboard/admin/models" className="ps-nav-link">💠 Models</Link>
              <Link to="/dashboard/admin/errors" className="ps-nav-link">⚠️ Error Logs</Link>
              <Link to="/dashboard/profile" className="ps-nav-link active">👤 Profile <span className="ps-chevron">›</span></Link>
            </>
          ) : (
            <>
              <Link to="/dashboard" className="ps-nav-link">▦ Dashboard</Link>
              <Link to="/dashboard/submit" className="ps-nav-link">⬆ Submit Paper</Link>
              <Link to="/dashboard/jobs" className="ps-nav-link">⏱ Analysis Jobs</Link>
              <Link to="/dashboard/history" className="ps-nav-link">🕘 History</Link>
              <Link to="/dashboard/profile" className="ps-nav-link active">👤 Profile <span className="ps-chevron">›</span></Link>
            </>
          )}
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
          {/* Dynamically update the role badge as well to avoid confusion */}
          <span className={`ps-role-badge ${isAdmin ? 'ps-role-admin' : ''}`}>
            {isAdmin ? 'Administrator' : 'Researcher'}
          </span>
        </header>

        {/* Isolated Scoped Area */}
        <div className="ps-page-container ps-profile-scope">
          <div className="ps-profile-heading">
            <h1 className="ps-profile-title">Profile</h1>
            <p className="ps-profile-subtitle">Manage your account settings.</p>
          </div>

          <div className="ps-profile-grid">
            {/* Account Info Card */}
            <div className="ps-profile-card">
              <div className="ps-profile-card-header">
                <h3 className="ps-profile-card-label"><UserIcon /> Personal Information</h3>
              </div>
              <div className="ps-profile-card-body">
                <form onSubmit={handleSave} className="ps-profile-form">
                  <div className="ps-profile-row">
                    <div className="ps-profile-group">
                      <label>First Name</label>
                      <input value={firstName} onChange={e => setFirstName(e.target.value)} required />
                    </div>
                    <div className="ps-profile-group">
                      <label>Last Name</label>
                      <input value={lastName} onChange={e => setLastName(e.target.value)} required />
                    </div>
                  </div>
                  <div className="ps-profile-group">
                    <label>Email</label>
                    <input className="ps-profile-readonly" value={user.email || ''} disabled />
                  </div>
                  <div className="ps-profile-group">
                    <label>Role</label>
                    <input className="ps-profile-readonly" value={isAdmin ? 'Administrator' : 'Researcher'} disabled />
                  </div>
                  <button type="submit" className="ps-profile-submit-btn" disabled={saving}>
                    {saving && <Loader2 />} Save Changes
                  </button>
                </form>
              </div>
            </div>

            {/* Security Card */}
            <div className="ps-profile-card">
              <div className="ps-profile-card-header">
                <h3 className="ps-profile-card-label"><LockIcon /> Change Password</h3>
                <p className="ps-profile-card-desc">Update your password to keep your account secure.</p>
              </div>
              <div className="ps-profile-card-body">
                <form className="ps-profile-form" onSubmit={e => e.preventDefault()}>
                  <div className="ps-profile-group">
                    <label>Current Password</label>
                    <input type="password" placeholder="••••••••" required />
                  </div>
                  <div className="ps-profile-group">
                    <label>New Password</label>
                    <input type="password" placeholder="Min 6 characters" required />
                  </div>
                  <div className="ps-profile-group">
                    <label>Confirm New Password</label>
                    <input type="password" placeholder="••••••••" required />
                  </div>
                  <button type="submit" className="ps-profile-submit-btn">Update Password</button>
                </form>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}