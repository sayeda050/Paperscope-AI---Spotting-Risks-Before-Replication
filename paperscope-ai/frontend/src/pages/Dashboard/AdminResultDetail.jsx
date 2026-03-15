import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, TrendingUp } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getAdminResultDetail } from "../../api/analysis.api.js";
import "./Dashboard.css";
import "./AdminDashboard.css";
import "./AdminResultDetail.css";

function formatRiskLabel(label) {
  if (label === "High") return "High Risk";
  if (label === "Med") return "Medium Risk";
  if (label === "Low") return "Low Risk";
  return label || "Unknown Risk";
}

export default function AdminResultDetail() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();
  const { resultId } = useParams();

  const [result, setResult] = useState(null);
  const [loadingResult, setLoadingResult] = useState(true);

  useEffect(() => {
    if (!initializing) {
      if (!user) {
        navigate("/login");
      } else if (!user.is_superuser && user.role !== "ADMIN") {
        navigate("/dashboard");
      }
    }
  }, [user, initializing, navigate]);

  useEffect(() => {
    if (!initializing && user && (user.is_superuser || user.role === "ADMIN") && resultId) {
      loadResult();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initializing, user, resultId]);

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

  async function loadResult() {
    try {
      setLoadingResult(true);

      const data = await getAdminResultDetail(resultId);
      const resultObj = data?.result || {};
      const explanation = resultObj.explanation_json || {};

      const normalized = {
        title: data?.paper_title || "Untitled Paper",
        completedAt: resultObj.completed_at
          ? new Date(resultObj.completed_at).toLocaleString()
          : "—",
        score: Number(resultObj.risk_score || 0),
        riskLabel: formatRiskLabel(resultObj.risk_label),
        summary:
          explanation.summary ||
          "No summary was generated for this result.",
        factors:
          Array.isArray(explanation.topFactors) && explanation.topFactors.length > 0
            ? explanation.topFactors
            : ["No contributing factors were provided."],
        sections:
          Array.isArray(explanation.sections) && explanation.sections.length > 0
            ? explanation.sections.map((section) => ({
                name: section.name || "Section",
                score: Number(section.score || 0),
                note: section.detail || section.note || "No section note available.",
              }))
            : [],
        keywords:
          Array.isArray(explanation.keywords) && explanation.keywords.length > 0
            ? explanation.keywords
            : [],
      };

      setResult(normalized);
    } catch (err) {
      setResult(null);
    } finally {
      setLoadingResult(false);
    }
  }

  if (loadingResult) {
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
                <p className="ps-user-name">{user.first_name} {user.last_name}</p>
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
            <div className="admin-detail-wrap">
              <Link to="/dashboard/admin/results" className="admin-detail-back">
                <ArrowLeft size={18} />
                <span>Back</span>
              </Link>

              <div className="admin-detail-empty">
                <h1>Loading result...</h1>
                <p>Please wait while the analysis result is being loaded.</p>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (!result) {
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
                <p className="ps-user-name">{user.first_name} {user.last_name}</p>
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
            <div className="admin-detail-wrap">
              <Link to="/dashboard/admin/results" className="admin-detail-back">
                <ArrowLeft size={18} />
                <span>Back</span>
              </Link>

              <div className="admin-detail-empty">
                <h1>Result not found</h1>
                <p>The requested analysis result does not exist.</p>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  const riskClass =
    result.riskLabel === "High Risk"
      ? "admin-detail-risk-pill high"
      : result.riskLabel === "Medium Risk"
      ? "admin-detail-risk-pill medium"
      : "admin-detail-risk-pill low";

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
              <p className="ps-user-name">{user.first_name} {user.last_name}</p>
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
          <div className="admin-detail-wrap">
            <Link to="/dashboard/admin/results" className="admin-detail-back">
              <ArrowLeft size={18} />
              <span>Back</span>
            </Link>

            <div className="admin-detail-header">
              <h1>{result.title}</h1>
              <p>Analysis completed {result.completedAt}</p>
            </div>

            <div className="admin-detail-top-grid">
              <div className="admin-detail-score-card">
                <p className="admin-detail-score-label">Risk Score</p>
                <div className="admin-detail-score-value">{Math.round(result.score)}</div>
                <div className={riskClass}>{result.riskLabel}</div>
                <div className="admin-detail-score-track">
                  <div
                    className="admin-detail-score-fill"
                    style={{ width: `${Math.max(0, Math.min(100, Number(result.score || 0)))}%` }}
                  />
                </div>
              </div>

              <div className="admin-detail-summary-card">
                <div className="admin-detail-card-title">
                  <TrendingUp size={18} />
                  <span>Summary</span>
                </div>

                <p className="admin-detail-summary-text">{result.summary}</p>

                <h3>Top Contributing Factors</h3>
                <ul className="admin-detail-factor-list">
                  {result.factors.map((factor) => (
                    <li key={factor}>{factor}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="admin-detail-bottom-grid">
              <div className="admin-detail-sections-card">
                <h2>Section-Level Scores</h2>

                <div className="admin-detail-section-list">
                  {result.sections.map((section) => (
                    <div key={section.name} className="admin-detail-section-item">
                      <div className="admin-detail-section-head">
                        <span>{section.name}</span>
                        <span>{section.score}/100</span>
                      </div>
                      <div className="admin-detail-section-track">
                        <div
                          className={`admin-detail-section-fill ${
                            section.score >= 75
                              ? "high"
                              : section.score >= 50
                              ? "medium"
                              : "low"
                          }`}
                          style={{ width: `${section.score}%` }}
                        />
                      </div>
                      <p>{section.note}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="admin-detail-keywords-card">
                <h2>Keywords</h2>
                <div className="admin-detail-keywords-wrap">
                  {result.keywords.map((keyword) => (
                    <span key={keyword} className="admin-detail-keyword-chip">
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ height: 18 }} />
          </div>
        </div>
      </main>
    </div>
  );
}