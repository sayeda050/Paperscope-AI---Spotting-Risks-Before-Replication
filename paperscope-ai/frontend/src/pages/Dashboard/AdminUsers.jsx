import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { 
  Shield, LayoutGrid, Users, FileText, Clock, 
  Database, Cpu, AlertTriangle, User, LogOut, 
  Search, ChevronRight 
} from 'lucide-react';
import './AdminUsers.css';

export default function AdminUsers() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, initializing } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');

  // Protect Admin Route
  useEffect(() => {
    if (!initializing) {
      if (!user) {
        navigate('/login');
      } else if (!user.is_superuser && user.role !== 'ADMIN') {
        navigate('/dashboard');
      }
    }
  }, [user, initializing, navigate]);

  // Hardcoded data based on the provided UI mockup
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

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f8fafc]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#0d9488]"></div>
      </div>
    );
  }

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Dynamically fetch user details
  const initials = `${user?.first_name?.[0] || 'A'}${user?.last_name?.[0] || 'T'}`.toUpperCase();
  const fullName = user?.first_name ? `${user.first_name} ${user.last_name}` : 'Anindita Tabassum';
  const email = user?.email || 'anindita.lubaba@gmail.com';

  return (
    <div className="admin-layout">
      {/* Sidebar Navigation - Matches Image 2 */}
      <aside className="admin-sidebar">
        <div className="sidebar-brand">
          <Shield className="brand-icon" />
          <span>PaperScope AI</span>
        </div>

        <div className="sidebar-section">ADMINISTRATION</div>
        
        <nav className="sidebar-nav">
          <Link to="/dashboard/admin" className={`nav-item ${location.pathname === '/dashboard/admin' ? 'active' : ''}`}>
            <LayoutGrid className="nav-icon" />
            <span>Dashboard</span>
          </Link>
          
          <Link to="/dashboard/admin/users" className={`nav-item ${location.pathname.includes('/users') ? 'active' : ''}`}>
            <Users className="nav-icon" />
            <span>Users</span>
            <ChevronRight className="nav-chevron-active" size={16} />
          </Link>

          <Link to="/dashboard/admin/papers" className="nav-item">
            <FileText className="nav-icon" />
            <span>Papers</span>
          </Link>

          <Link to="/dashboard/jobs" className="nav-item">
            <Clock className="nav-icon" />
            <span>Jobs</span>
          </Link>

          <Link to="/dashboard/results" className="nav-item">
            <Database className="nav-icon" />
            <span>Results</span>
          </Link>

          <Link to="/dashboard/models" className="nav-item">
            <Cpu className="nav-icon" />
            <span>Models</span>
          </Link>

          <Link to="/dashboard/errors" className="nav-item">
            <AlertTriangle className="nav-icon" />
            <span>Error Logs</span>
          </Link>

          <Link to="/dashboard/profile" className="nav-item">
            <User className="nav-icon" />
            <span>Profile</span>
          </Link>
        </nav>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="avatar">{initials}</div>
            <div className="user-info">
              <span className="user-name">{fullName}</span>
              <span className="user-email">{email}</span>
            </div>
          </div>
          <button className="sign-out-btn" onClick={handleLogout}>
            <LogOut className="nav-icon" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="admin-main">
        <header className="admin-topbar">
          <div className="topbar-spacer"></div>
          <div className="admin-badge">Admin</div>
        </header>

        <div className="admin-content">
          <h1 className="page-title">Manage Users</h1>
          <p className="page-subtitle">View and manage all registered users.</p>

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