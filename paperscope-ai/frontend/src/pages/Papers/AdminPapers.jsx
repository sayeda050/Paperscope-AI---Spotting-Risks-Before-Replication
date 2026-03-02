import React, { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { 
  Shield, LayoutGrid, Users, FileText, Clock, 
  Database, Cpu, AlertTriangle, User, LogOut, ChevronRight
} from 'lucide-react';

// Mock data perfectly matching the exact items in your 1st picture
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

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
      </div>
    );
  }

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Safe fallback for user initials
  const initials = `${user?.first_name?.[0] || 'A'}${user?.last_name?.[0] || 'D'}`.toUpperCase();
  const fullName = user?.first_name ? `${user.first_name} ${user.last_name}` : 'Admin User';
  const email = user?.email || 'admin@paperscope.ai';

  return (
    <div className="flex h-screen bg-[#f8fafc] font-sans overflow-hidden text-slate-900">
      
      {/* SIDEBAR (Dark Navy, matching Pic 1) */}
      <aside className="w-64 bg-[#111827] text-slate-300 flex flex-col flex-shrink-0">
        {/* Brand Header */}
        <div className="h-20 flex items-center px-6 gap-3 text-white">
          <Shield className="w-7 h-7 text-emerald-400" />
          <span className="font-bold text-xl tracking-wide">PaperScope AI</span>
        </div>

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto py-4 px-3 flex flex-col gap-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 px-3 mt-4">
            Administration
          </p>
          
          <Link to="/dashboard/admin" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-800 hover:text-white transition-colors">
            <LayoutGrid className="w-5 h-5 opacity-70" />
            <span className="font-medium text-sm">Dashboard</span>
          </Link>
          
          <Link to="/dashboard/admin/users" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-800 hover:text-white transition-colors">
            <Users className="w-5 h-5 opacity-70" />
            <span className="font-medium text-sm">Users</span>
          </Link>
          
          {/* Active Link: Papers */}
          <Link to="/dashboard/admin/papers" className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-[#1e293b] text-emerald-400 transition-colors">
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5" />
              <span className="font-medium text-sm">Papers</span>
            </div>
            <ChevronRight className="w-4 h-4 opacity-70" />
          </Link>
          
          <Link to="/dashboard/admin/jobs" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-800 hover:text-white transition-colors">
            <Clock className="w-5 h-5 opacity-70" />
            <span className="font-medium text-sm">Jobs</span>
          </Link>
          
          <Link to="/dashboard/admin/results" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-800 hover:text-white transition-colors">
            <Database className="w-5 h-5 opacity-70" />
            <span className="font-medium text-sm">Results</span>
          </Link>
          
          <Link to="/dashboard/admin/models" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-800 hover:text-white transition-colors">
            <Cpu className="w-5 h-5 opacity-70" />
            <span className="font-medium text-sm">Models</span>
          </Link>
          
          <Link to="/dashboard/admin/errors" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-800 hover:text-white transition-colors">
            <AlertTriangle className="w-5 h-5 opacity-70" />
            <span className="font-medium text-sm">Error Logs</span>
          </Link>

          <Link to="/dashboard/profile" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-800 hover:text-white transition-colors">
            <User className="w-5 h-5 opacity-70" />
            <span className="font-medium text-sm">Profile</span>
          </Link>
        </div>

        {/* User Profile & Logout */}
        <div className="p-4 border-t border-slate-800/60">
          <div className="flex items-center gap-3 px-2 py-2 mb-2">
            <div className="w-9 h-9 rounded-full bg-emerald-500 text-white flex items-center justify-center text-sm font-bold">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{fullName}</p>
              <p className="text-xs text-slate-400 truncate">{email}</p>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-colors text-sm font-medium"
          >
            <LogOut className="w-5 h-5 opacity-70" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-white">
        
        {/* Top Navbar */}
        <header className="h-16 flex items-center justify-end px-8 border-b border-gray-100 shrink-0">
          <span className="px-4 py-1.5 bg-emerald-50 text-emerald-700 text-sm font-medium rounded-full">
            Admin
          </span>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto p-8 lg:p-12">
          <div className="max-w-5xl mx-auto">
            
            {/* Header Text */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Manage Papers</h1>
              <p className="text-slate-500 mt-2 text-base">All submitted papers across the platform.</p>
            </div>

            {/* Table Container */}
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse whitespace-nowrap">
                  <thead>
                    <tr className="border-b border-gray-200 text-sm text-slate-500 bg-white">
                      <th className="font-medium py-4 px-6 w-1/2">Title</th>
                      <th className="font-medium py-4 px-6">Submitter</th>
                      <th className="font-medium py-4 px-6">Source</th>
                      <th className="font-medium py-4 px-6">Uploaded</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {mockPapers.map((paper) => (
                      <tr key={paper.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="py-4 px-6 text-sm text-slate-800">
                          {paper.title}
                        </td>
                        <td className="py-4 px-6 text-sm text-slate-500">
                          {paper.submitter}
                        </td>
                        <td className="py-4 px-6">
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">
                            {paper.source}
                          </span>
                        </td>
                        <td className="py-4 px-6 text-sm text-slate-500">
                          {paper.uploaded}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      </main>
    </div>
  );
}