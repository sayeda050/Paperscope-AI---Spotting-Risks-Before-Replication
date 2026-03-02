import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { Search, AlertTriangle } from "lucide-react";
import "./Dashboard.css";
import "./AdminDashboard.css";
import "./ErrorLogs.css";

export default function ErrorLogs() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    if (!initializing) {
      if (!user) {
        navigate("/login");
      } else if (!user.is_superuser && user.role !== "ADMIN") {
        navigate("/dashboard");
      }
    }
  }, [user, initializing, navigate]);

  if (initializing) {
    return (
      <div className="ps-loading-screen">
        <div className="ps-loading-spinner"></div>
        <p>Verifying admin session...</p>
      </div>
    );
  }

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const logs = [
    {
      id: 1,
      source: "pdf_extraction",
      timestamp: "1/22/2025, 6:03:00 AM",
      message:
        "PDF extraction failed: corrupted file header at byte offset 1024. PyMuPDF raised fitz.FileDataError.",
      user: "Alex Rivera",
      paper: "Statistical Methods for Climate Model Validation",
    },
    {
      id: 2,
      source: "arxiv_api",
      timestamp: "1/25/2025, 10:30:00 AM",
      message: "arXiv API rate limit exceeded. Retry after 60s.",
      user: "",
      paper: "",
    },
    {
      id: 3,
      source: "text_preprocessing",
      timestamp: "2/14/2025, 5:13:00 AM",
      message:
        "NLTK punkt tokenizer not found. Falling back to whitespace tokenization.",
      user: "Mike Thompson",
      paper: "Reinforcement Learning in Autonomous Navigation",
    },
    {
      id: 4,
      source: "model_loader",
      timestamp: "2/15/2025, 3:00:00 AM",
      message: "Model artifact cache miss for mv2. Reloading from disk.",
      user: "",
      paper: "",
    },
  ];

  const filteredLogs = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();

    if (!term) return logs;

    return logs.filter((log) => {
      return (
        log.source.toLowerCase().includes(term) ||
        log.message.toLowerCase().includes(term) ||
        log.timestamp.toLowerCase().includes(term) ||
        log.user.toLowerCase().includes(term) ||
        log.paper.toLowerCase().includes(term)
      );
    });
  }, [searchTerm]);

  return (
    <div className="ps-app">
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>

        <div className="ps-nav-section">
          <p className="ps-nav-label">ADMINISTRATION</p>
          <Link to="/dashboard/admin" className="ps-nav-link">
            ▦ Dashboard
          </Link>
          <Link to="/dashboard/admin/users" className="ps-nav-link">
            👥 Users
          </Link>
          <Link to="/dashboard/admin/papers" className="ps-nav-link">
            📄 Papers
          </Link>
          <Link to="/dashboard/admin/jobs" className="ps-nav-link">
            ⏱ Jobs
          </Link>
          <Link to="/dashboard/admin/results" className="ps-nav-link">
            🗄️ Results
          </Link>
          <Link to="/dashboard/admin/models" className="ps-nav-link">
            💠 Models
          </Link>
          <Link to="/dashboard/admin/errors" className="ps-nav-link active">
            ⚠️ Error Logs <span className="ps-chevron">›</span>
          </Link>
          <Link to="/dashboard/profile" className="ps-nav-link">
            👤 Profile
          </Link>
        </div>

        <div className="ps-sidebar-footer">
          <div className="ps-user-card">
            <div className="ps-user-avatar">
              {user.first_name?.[0] || ""}
              {user.last_name?.[0] || ""}
            </div>
            <div className="ps-user-meta">
              <p className="ps-user-name">
                {user.first_name} {user.last_name}
              </p>
              <p className="ps-user-email">{user.email}</p>
            </div>
          </div>
          <button className="ps-btn-logout" onClick={handleLogout}>
            ⎋ Sign Out
          </button>
        </div>
      </aside>

      <main className="ps-main">
        <div className="ps-topbar">
          <div />
          <div className="ps-role-pill ps-role-admin">Administrator</div>
        </div>

        <div className="ps-content">
          <div className="error-logs-content">
            <div className="error-logs-header">
              <h1>Error Logs</h1>
              <p>System error logs for monitoring and debugging.</p>
            </div>

            <div className="error-search-wrap">
              <Search size={18} className="error-search-icon" />
              <input
                type="text"
                placeholder="Search logs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>

            <div className="error-log-list">
              {filteredLogs.length > 0 ? (
                filteredLogs.map((log) => (
                  <div className="error-log-card" key={log.id}>
                    <div className="error-log-meta">
                      <span className="error-log-tag">{log.source}</span>
                      <span className="error-log-time">{log.timestamp}</span>
                    </div>

                    <p className="error-log-message">{log.message}</p>

                    {(log.user || log.paper) && (
                      <p className="error-log-extra">
                        {log.user && (
                          <>
                            <span className="error-log-label">User:</span>{" "}
                            {log.user}
                          </>
                        )}

                        {log.user && log.paper && (
                          <span className="error-log-separator"> </span>
                        )}

                        {log.paper && (
                          <>
                            <span className="error-log-label">Paper:</span>{" "}
                            {log.paper}
                          </>
                        )}
                      </p>
                    )}
                  </div>
                ))
              ) : (
                <div className="error-empty-state">
                  <AlertTriangle size={42} />
                  <h3>No matching logs found</h3>
                  <p>Try a different keyword to search the logs.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}