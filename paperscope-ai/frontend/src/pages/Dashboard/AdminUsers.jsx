import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getAdminUsers } from '../../api/analysis.api.js';
import { Search } from 'lucide-react';
import './Dashboard.css';
import './AdminUsers.css';

export default function AdminUsers() {
  const navigate = useNavigate();
  const { user, logout, initializing } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');
  const [usersData, setUsersData] = useState([]);

  useEffect(() => {
    if (!initializing) {
      if (!user) navigate('/login');
      else if (!user.is_superuser && user.role !== 'ADMIN') navigate('/dashboard');
      else loadUsers();
    }
  }, [user, initializing, navigate]);

  async function loadUsers() {
    try {
      const data = await getAdminUsers();
      setUsersData(data.users || []);
    } catch (err) {
      console.error(err);
    }
  }

  const filteredUsers = useMemo(() => usersData.filter((u) => u.name.toLowerCase().includes(searchTerm.toLowerCase()) || u.email.toLowerCase().includes(searchTerm.toLowerCase())), [usersData, searchTerm]);
  if (initializing) return null;
  if (!user) return null;
  const handleLogout = async () => { await logout(); navigate('/login'); };

  return (
    <div className="ps-app"><aside className="ps-sidebar"><div className="ps-brand"><div className="ps-logo-shield">🛡️</div><span className="ps-brand-name">PaperScope AI</span></div><div className="ps-nav-section"><p className="ps-nav-label">ADMINISTRATION</p><Link to="/dashboard/admin" className="ps-nav-link">▦ Dashboard</Link><Link to="/dashboard/admin/users" className="ps-nav-link active">👥 Users <span className="ps-chevron">›</span></Link><Link to="/dashboard/admin/papers" className="ps-nav-link">📄 Papers</Link><Link to="/dashboard/admin/jobs" className="ps-nav-link">⏱ Jobs</Link><Link to="/dashboard/admin/results" className="ps-nav-link">🗄️ Results</Link><Link to="/dashboard/admin/models" className="ps-nav-link">💠 Models</Link><Link to="/dashboard/admin/errors" className="ps-nav-link">⚠️ Error Logs</Link><Link to="/dashboard/profile" className="ps-nav-link">👤 Profile</Link></div><div className="ps-sidebar-footer"><div className="ps-user-card"><div className="ps-user-avatar">{user?.first_name?.[0] || ""}{user?.last_name?.[0] || ""}</div><div className="ps-user-meta"><p className="ps-user-name">{user?.first_name} {user?.last_name}</p><p className="ps-user-email">{user?.email}</p></div></div><button className="ps-btn-logout" onClick={handleLogout}>⎋ Sign Out</button></div></aside>
      <main className="ps-main"><header className="ps-topbar"><div /><div className="ps-role-pill ps-role-admin">Administrator</div></header><div className="ps-content"><h1 className="ps-title">Manage Users</h1><p className="ps-subtitle">View and manage all registered users.</p><div className="search-container"><Search className="search-icon" /><input type="text" placeholder="Search users..." className="search-input" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} /></div><div className="table-container"><table className="users-table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Joined</th></tr></thead><tbody>{filteredUsers.map((userItem) => <tr key={userItem.user_id}><td className="font-medium">{userItem.name}</td><td className="text-muted">{userItem.email}</td><td><span className={`role-pill ${userItem.role === 'Admin' ? 'role-admin' : 'role-user'}`}>{userItem.role}</span></td><td className="text-muted">{new Date(userItem.joined).toLocaleDateString()}</td></tr>)}</tbody></table></div></div></main></div>
  );
}
