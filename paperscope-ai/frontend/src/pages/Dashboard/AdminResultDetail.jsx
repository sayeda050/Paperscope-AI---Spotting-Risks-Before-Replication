import React, { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, TrendingUp } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext.jsx";
import "./Dashboard.css";
import "./AdminDashboard.css";
import "./AdminResultDetail.css";

export default function AdminResultDetail() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();
  const { resultId } = useParams();

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

  const resultsMap = {
    r1: {
      title: "Deep Learning for Protein Folding: A Reproducibility Study",
      completedAt: "1/10/2025, 4:05:00 AM",
      score: 72,
      riskLabel: "High Risk",
      summary:
        "This paper presents significant reproducibility risks due to missing dataset availability, lack of statistical rigor in reported results, and insufficient documentation of hyperparameter optimization.",
      factors: [
        "Missing dataset availability statement",
        "No confidence intervals reported",
        "Single random seed used",
        "Hyperparameter search not documented",
      ],
      sections: [
        {
          name: "Methodology",
          score: 65,
          note: "Methods described at high level but lack implementation specifics",
        },
        {
          name: "Data Availability",
          score: 82,
          note: "No data sharing statement; proprietary dataset mentioned",
        },
        {
          name: "Statistical Rigor",
          score: 78,
          note: "Results reported without confidence intervals or variance",
        },
        {
          name: "Code Availability",
          score: 60,
          note: "GitHub link provided but repository is empty",
        },
      ],
      keywords: [
        "deep learning",
        "protein folding",
        "reproducibility",
        "neural network",
        "benchmark",
      ],
    },
    r2: {
      title: "Attention Mechanisms in Low-Resource NLP",
      completedAt: "1/15/2025, 11:20:00 AM",
      score: 34,
      riskLabel: "Low Risk",
      summary:
        "This paper appears comparatively reproducible. It includes a clearer methodology, stronger reporting discipline, and sufficient implementation detail for replication.",
      factors: [
        "Public dataset referenced",
        "Model settings documented",
        "Evaluation protocol clearly defined",
      ],
      sections: [
        {
          name: "Methodology",
          score: 28,
          note: "Well-structured and detailed experimental setup",
        },
        {
          name: "Data Availability",
          score: 22,
          note: "Public datasets and preprocessing steps listed",
        },
        {
          name: "Statistical Rigor",
          score: 36,
          note: "Includes repeated runs and standard deviation reporting",
        },
        {
          name: "Code Availability",
          score: 44,
          note: "Code referenced but installation notes are limited",
        },
      ],
      keywords: ["attention", "nlp", "low-resource", "transformer", "evaluation"],
    },
    r3: {
      title: "Reinforcement Learning in Autonomous Navigation",
      completedAt: "2/14/2025, 5:13:00 AM",
      score: 55,
      riskLabel: "Medium Risk",
      summary:
        "This paper shows moderate reproducibility concerns, mainly around training setup clarity and partial reporting of environment settings.",
      factors: [
        "Environment settings only partially documented",
        "Reward shaping details are limited",
        "Insufficient ablation discussion",
      ],
      sections: [
        {
          name: "Methodology",
          score: 58,
          note: "Core method described, but training details are incomplete",
        },
        {
          name: "Data Availability",
          score: 40,
          note: "Simulation assets partially referenced",
        },
        {
          name: "Statistical Rigor",
          score: 61,
          note: "Some metrics reported, but variance details are thin",
        },
        {
          name: "Code Availability",
          score: 59,
          note: "Repository mentioned but missing reproducible setup docs",
        },
      ],
      keywords: ["reinforcement learning", "autonomous navigation", "simulation", "benchmark"],
    },
    r4: {
      title: "Generative Adversarial Networks for Medical Imaging",
      completedAt: "2/18/2025, 8:45:00 AM",
      score: 67,
      riskLabel: "High Risk",
      summary:
        "This paper raises concerns due to limited dataset transparency, unclear preprocessing flow, and insufficient reporting of validation safeguards.",
      factors: [
        "Dataset access restrictions unclear",
        "Preprocessing pipeline incompletely described",
        "Validation safeguards not fully specified",
      ],
      sections: [
        {
          name: "Methodology",
          score: 63,
          note: "Architecture described but training procedure lacks detail",
        },
        {
          name: "Data Availability",
          score: 79,
          note: "Data source mentioned without replication access guidance",
        },
        {
          name: "Statistical Rigor",
          score: 70,
          note: "Limited robustness analysis included",
        },
        {
          name: "Code Availability",
          score: 56,
          note: "No maintained public implementation linked",
        },
      ],
      keywords: ["gan", "medical imaging", "segmentation", "reproducibility"],
    },
  };

  const result = resultsMap[resultId];

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
                <div className="admin-detail-score-value">{result.score}</div>
                <div className={riskClass}>{result.riskLabel}</div>
                <div className="admin-detail-score-track">
                  <div
                    className="admin-detail-score-fill"
                    style={{ width: `${result.score}%` }}
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