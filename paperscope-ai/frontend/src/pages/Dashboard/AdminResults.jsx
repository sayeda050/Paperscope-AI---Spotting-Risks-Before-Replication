import React, { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import "./Dashboard.css";
import "./AdminDashboard.css";
import "./AdminResults.css";

export default function AdminResults() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();

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

  const results = [
    {
      id: "r1",
      paper: "Deep Learning for Protein Folding: A Reproducibility Study",
      score: 72,
      level: "High Risk",
      completed: "1/10/2025",
      detailUrl: "/dashboard/admin/results/r1",
    },
    {
      id: "r2",
      paper: "Attention Mechanisms in Low-Resource NLP",
      score: 34,
      level: "Low Risk",
      completed: "1/15/2025",
      detailUrl: "/dashboard/admin/results/r2",
    },
    {
      id: "r3",
      paper: "Reinforcement Learning in Autonomous Navigation",
      score: 55,
      level: "Medium Risk",
      completed: "2/14/2025",
      detailUrl: "/dashboard/admin/results/r3",
    },
    {
      id: "r4",
      paper: "Generative Adversarial Networks for Medical Imaging",
      score: 67,
      level: "High Risk",
      completed: "2/18/2025",
      detailUrl: "/dashboard/admin/results/r4",
    },
  ];

  const getRiskClass = (level) => {
    if (level === "High Risk") return "admin-result-pill high";
    if (level === "Medium Risk") return "admin-result-pill medium";
    return "admin-result-pill low";
  };

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
          <Link to="/dashboard/admin/results" className="ps-nav-link active">
            🗄️ Results <span className="ps-chevron">›</span>
          </Link>
          <Link to="/dashboard/admin/models" className="ps-nav-link">
            💠 Models
          </Link>
          <Link to="/dashboard/admin/errors" className="ps-nav-link">
            ⚠️ Error Logs
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
          <div className="admin-results-wrap">
            <div className="admin-results-header">
              <h1>Analysis Results</h1>
              <p>System-wide analysis results overview.</p>
            </div>

            <div className="admin-results-card">
              <div className="admin-results-table-wrap">
                <table className="admin-results-table">
                  <thead>
                    <tr>
                      <th>Paper</th>
                      <th>Risk Score</th>
                      <th>Risk Level</th>
                      <th>Completed</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((result) => (
                      <tr key={result.id}>
                        <td className="paper-cell">
                          <span className="paper-title-text">{result.paper}</span>
                        </td>
                        <td className="score-cell">{result.score}/100</td>
                        <td>
                          <span className={getRiskClass(result.level)}>
                            {result.level}
                          </span>
                        </td>
                        <td className="date-cell">{result.completed}</td>
                        <td className="detail-cell">
                          <Link
                            to={result.detailUrl}
                            className="detail-icon-btn"
                            aria-label={`View result for ${result.paper}`}
                          >
                            <Eye size={18} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div style={{ height: 18 }} />
          </div>
        </div>
      </main>
    </div>
  );
}