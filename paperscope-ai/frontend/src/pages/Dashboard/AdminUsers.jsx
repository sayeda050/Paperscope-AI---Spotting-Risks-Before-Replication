import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { Search } from 'lucide-react';
import './Dashboard.css';
import './AdminUsers.css';

export default function AdminUsers() {
  const navigate = useNavigate();
  const { user, logout, initializing } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (!initializing) {
      if (!user) {
        navigate('/login');
      } else if (!user.is_superuser && user.role !== 'ADMIN') {
        navigate('/dashboard');
      }
    }
  }, [user, initializing, navigate]);

  const usersData = [
    { id: 1, name: 'Sarah Chen', email: 'admin@paperscope.ai', role: 'Admin', joined: '11/1/2024' },
    { id: 2, name: 'Alex Rivera', email: 'demo@paperscope.ai', role: 'User', joined: '12/15/2024' },
    { id: 3, name: 'Jane Park', email: 'jane@university.edu', role: 'User', joined: '1/5/2025' },
    { id: 4, name: 'Mike Thompson', email: 'mike@research.org', role: 'User', joined: '1/20/2025' },
    { id: 5, name: 'Lisa Wang', email: 'lisa@lab.edu', role: 'User', joined: '2/1/2025' },
  ];

  const filteredUsers = usersData.filter(u => 
    u.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    u.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (initializing) return null;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="ps-app">
      {/* SIDEBAR - MATCHES ADMIN DASHBOARD EXACTLY */}
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>
        <div className="ps-nav-section">
          <p className="ps-nav-label">ADMINISTRATION</p>
          <Link to="/dashboard/admin" className="ps-nav-link">▦ Dashboard</Link>
          <Link to="/dashboard/admin/users" className="ps-nav-link active">👥 Users <span className="ps-chevron">›</span></Link>
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
              {user?.first_name?.[0] || ""}{user?.last_name?.[0] || ""}
            </div>
            <div className="ps-user-meta">
              <p className="ps-user-name">{user?.first_name} {user?.last_name}</p>
              <p className="ps-user-email">{user?.email}</p>
            </div>
          </div>
          <button className="ps-btn-logout" onClick={handleLogout}>⎋ Sign Out</button>
        </div>
      </aside>

      {/* Main Content Area - UNCHANGED */}
      <main className="ps-main">
        <header className="ps-topbar">
          <div />
          <div className="ps-role-pill ps-role-admin">Administrator</div>
        </header>

        <div className="ps-content">
          <h1 className="ps-title">Manage Users</h1>
          <p className="ps-subtitle">View and manage all registered users.</p>

          <div className="search-container">
            <Search className="search-icon" />
            <input 
              type="text" 
              placeholder="Search users..." 
              className="search-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="table-container">
            <table className="users-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Joined</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((userItem) => (
                  <tr key={userItem.id}>
                    <td className="font-medium">{userItem.name}</td>
                    <td className="text-muted">{userItem.email}</td>
                    <td>
                      <span className={`role-pill ${userItem.role === 'Admin' ? 'role-admin' : 'role-user'}`}>
                        {userItem.role}
                      </span>
                    </td>
                    <td className="text-muted">{userItem.joined}</td>
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