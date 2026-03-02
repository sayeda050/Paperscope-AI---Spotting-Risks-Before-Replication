import React, { useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { 
  Shield, LayoutGrid, Users, FileText, Clock, 
  Database, Cpu, AlertTriangle, User, LogOut, ChevronRight
} from 'lucide-react';

// Mock data perfectly matching the exact items in your picture
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
  const location = useLocation();

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
  const initials = `${user?.first_name?.[0] || 'S'}${user?.last_name?.[0] || 'C'}`.toUpperCase();
  const fullName = user?.first_name ? `${user.first_name} ${user.last_name}` : 'Sarah Chen';
  const email = user?.email || 'admin@paperscope.ai';

  return (
    <div className="flex h-screen bg-[#f8fafc] font-sans overflow-hidden text-slate-900">
      
      {/* SIDEBAR */}
      <aside className="w-[260px] bg-[#0f172a] text-[#cbd5e1] flex flex-col flex-shrink-0">
        {/* Brand Header */}
        <div className="h-[73px] flex items-center px-6 gap-3 border-b border-[#1e293b]">
          <Shield className="w-6 h-6 text-[#0d9488]" />
          <span className="font-bold text-[1.15rem] text-white tracking-wide">PaperScope AI</span>
        </div>

        {/* Navigation */}
        <div className="flex-1 overflow-y-auto py-2 flex flex-col gap-1">
          <p className="text-[0.75rem] font-semibold text-[#64748b] uppercase tracking-[0.05em] mb-1 px-6 mt-4">
            Administration
          </p>
          
          <div className="px-3 flex flex-col gap-1 mt-2">
            <Link to="/dashboard/admin" className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${location.pathname === '/dashboard/admin' ? 'bg-[#1e293b] text-[#0d9488] font-medium' : 'hover:bg-[#1e293b] hover:text-white'}`}>
              <LayoutGrid className="w-[18px] h-[18px]" />
              <span className="text-[0.95rem]">Dashboard</span>
            </Link>
            
            <Link to="/dashboard/admin/users" className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${location.pathname.includes('/users') ? 'bg-[#1e293b] text-[#0d9488] font-medium' : 'hover:bg-[#1e293b] hover:text-white'}`}>
              <Users className="w-[18px] h-[18px]" />
              <span className="text-[0.95rem]">Users</span>
            </Link>
            
            {/* Active Link: Papers */}
            <Link to="/dashboard/admin/papers" className={`flex items-center justify-between px-3 py-2.5 rounded-lg transition-colors ${location.pathname.includes('/papers') ? 'bg-[#1e293b] text-[#0d9488] font-medium' : 'hover:bg-[#1e293b] hover:text-white'}`}>
              <div className="flex items-center gap-3">
                <FileText className="w-[18px] h-[18px]" />
                <span className="text-[0.95rem]">Papers</span>
              </div>
              <ChevronRight className="w-4 h-4 opacity-80" />
            </Link>
            
            <Link to="/dashboard/jobs" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#1e293b] hover:text-white transition-colors">
              <Clock className="w-[18px] h-[18px]" />
              <span className="text-[0.95rem]">Jobs</span>
            </Link>
            
            <Link to="/dashboard/history" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#1e293b] hover:text-white transition-colors">
              <Database className="w-[18px] h-[18px]" />
              <span className="text-[0.95rem]">Results</span>
            </Link>
            
            <Link to="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#1e293b] hover:text-white transition-colors">
              <Cpu className="w-[18px] h-[18px]" />
              <span className="text-[0.95rem]">Models</span>
            </Link>
            
            <Link to="#" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#1e293b] hover:text-white transition-colors">
              <AlertTriangle className="w-[18px] h-[18px]" />
              <span className="text-[0.95rem]">Error Logs</span>
            </Link>

            <Link to="/dashboard/profile" className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[#1e293b] hover:text-white transition-colors">
              <User className="w-[18px] h-[18px]" />
              <span className="text-[0.95rem]">Profile</span>
            </Link>
          </div>
        </div>

        {/* User Profile & Logout */}
        <div className="p-5 border-t border-[#1e293b] mt-auto">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-[36px] h-[36px] rounded-full bg-[#0d9488] text-white flex items-center justify-center text-[0.85rem] font-semibold">
              {initials}
            </div>
            <div className="flex-1 min-w-0 flex flex-col">
              <span className="text-[0.9rem] font-medium text-[#f1f5f9] truncate">{fullName}</span>
              <span className="text-[0.75rem] text-[#94a3b8] truncate">{email}</span>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-1 py-1 bg-transparent border-none text-[#cbd5e1] hover:text-white transition-colors text-[0.95rem] cursor-pointer"
          >
            <LogOut className="w-[18px] h-[18px]" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-white">
        
        {/* Top Navbar */}
        <header className="h-[64px] flex items-center justify-end px-8 border-b border-slate-100 shrink-0">
          <span className="px-4 py-1.5 bg-[#e6f8f6] text-[#0f766e] text-[0.85rem] font-medium rounded-[20px]">
            Admin
          </span>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto p-10 lg:p-12">
          <div className="max-w-[1100px] mx-auto">
            
            {/* Header Text */}
            <div className="mb-8">
              <h1 className="text-[1.75rem] font-bold text-[#0f172a] tracking-tight mb-2">Manage Papers</h1>
              <p className="text-[#64748b] text-[1.05rem]">All submitted papers across the platform.</p>
            </div>

            {/* Table Container */}
            <div className="bg-white border border-[#e2e8f0] rounded-[10px] overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse whitespace-nowrap">
                  <thead>
                    <tr className="border-b border-[#e2e8f0] text-[0.85rem] font-medium text-[#64748b] bg-white">
                      <th className="py-4 px-6 font-medium">Title</th>
                      <th className="py-4 px-6 font-medium">Submitter</th>
                      <th className="py-4 px-6 font-medium">Source</th>
                      <th className="py-4 px-6 font-medium">Uploaded</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#f1f5f9]">
                    {mockPapers.map((paper) => (
                      <tr key={paper.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="py-[18px] px-6 text-[0.95rem] font-medium text-[#0f172a]">
                          {paper.title}
                        </td>
                        <td className="py-[18px] px-6 text-[0.95rem] text-[#64748b]">
                          {paper.submitter}
                        </td>
                        <td className="py-[18px] px-6">
                          <span className="inline-flex items-center px-3 py-1 rounded-full text-[0.8rem] font-medium bg-[#f1f5f9] text-[#475569]">
                            {paper.source}
                          </span>
                        </td>
                        <td className="py-[18px] px-6 text-[0.95rem] text-[#64748b]">
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