import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import { getUserResult } from "../../api/analysis.api.js";
import "./AnalysisResult.css";

function mapRiskLabel(label) {
  if (label === "Low") return "Low";
  if (label === "Med") return "Medium";
  if (label === "High") return "High";
  return "Low";
}

export default function AnalysisResult() {
  const { jobId } = useParams();
  const { user, logout } = useAuth();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);

  if (!user) return null;

  useEffect(() => {
    loadResult();
  }, [jobId]);

  async function loadResult() {
    try {
      setLoading(true);
      const data = await getUserResult(jobId);
      const apiResult = data?.result;
      const explanationJson = apiResult?.explanation_json || {};

      setResult({
        jobId: String(jobId),
        paperTitle: data?.paper_title || 'Untitled Paper',
        completedAt: apiResult?.completed_at || null,
        riskScore: Number(apiResult?.risk_score || 0),
        riskLabel: mapRiskLabel(apiResult?.risk_label),
        explanationJson: {
          summary: explanationJson.summary || 'No summary available.',
          topFactors: Array.isArray(explanationJson.topFactors) ? explanationJson.topFactors : [],
          sections: Array.isArray(explanationJson.sections) ? explanationJson.sections : [],
          keywords: Array.isArray(explanationJson.keywords) ? explanationJson.keywords : [],
        }
      });
    } catch (error) {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="ps-dashboard-layout">
        <main className="ps-main-content">
          <p className="ps-muted-text">Loading result...</p>
          <Link to="/dashboard/jobs" className="ps-btn-outline" style={{ marginTop: '16px' }}>
             Back to Jobs
          </Link>
        </main>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="ps-dashboard-layout">
        <main className="ps-main-content">
          <p className="ps-muted-text">Result not found.</p>
          <Link to="/dashboard/jobs" className="ps-btn-outline" style={{marginTop: '16px'}}>
             Back to Jobs
          </Link>
        </main>
      </div>
    );
  }

  const riskColor = result.riskLabel === 'Low' ? 'ps-text-risk-low' : result.riskLabel === 'Medium' ? 'ps-text-risk-medium' : 'ps-text-risk-high';
  const riskBg = result.riskLabel === 'Low' ? 'ps-bg-risk-low' : result.riskLabel === 'Medium' ? 'ps-bg-risk-medium' : 'ps-bg-risk-high';

  return (
    <div className="ps-dashboard-layout">
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>
        <div className="ps-nav-section">
          <p className="ps-nav-label">NAVIGATION</p>
          <Link to="/dashboard" className="ps-nav-link">▦ Dashboard</Link>
          <Link to="/dashboard/submit" className="ps-nav-link">⬆ Submit Paper</Link>
          <Link to="/dashboard/jobs" className="ps-nav-link">⏱ Analysis Jobs</Link>
          <Link to="/dashboard/history" className="ps-nav-link">🕘 History</Link>
          <Link to="/dashboard/profile" className="ps-nav-link">👤 Profile</Link>
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
          <span className="ps-role-badge">Researcher</span>
        </header>

        <div className="ps-page-container">
          <div className="ps-mb-6">
            <Link to="/dashboard/jobs" className="ps-btn-ghost ps-mb-4">
               ← Back
            </Link>
            <h1 className="ps-view-title">{result.paperTitle}</h1>
            <p className="ps-view-subtitle">
              Analysis completed {result.completedAt ? new Date(result.completedAt).toLocaleString() : "—"}
            </p>
          </div>

          <div className="ps-grid-3 ps-mb-6">
            <div className="ps-card ps-card-shine ps-col-1 ps-text-center ps-p-6">
              <p className="ps-text-sm ps-muted-text ps-mb-2">Risk Score</p>
              <p className={`ps-text-6xl ps-font-extrabold ${riskColor}`}>{Math.round(result.riskScore)}</p>
              <div className="ps-mt-3">
                <span className={`ps-risk-badge ps-risk-badge-${result.riskLabel.toLowerCase()}`}>{result.riskLabel} Risk</span>
              </div>
              <div className="ps-progress-track ps-mt-4">
                <div className={`ps-progress-fill ${riskBg}`} style={{ width: `${result.riskScore}%` }} />
              </div>
            </div>

            <div className="ps-card ps-card-shine ps-col-2">
              <div className="ps-card-header">
                <h3 className="ps-card-title">📈 Summary</h3>
              </div>
              <div className="ps-card-content">
                <p className="ps-text-sm ps-leading-relaxed ps-muted-text">{result.explanationJson.summary}</p>
                <div className="ps-mt-4">
                  <p className="ps-text-sm ps-font-medium ps-mb-2">Top Contributing Factors</p>
                  <ul className="ps-space-y-1">
                    {result.explanationJson.topFactors.map((f, i) => (
                      <li key={i} className="ps-factor-item">
                        <span className="ps-factor-dot" /> {f}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <div className="ps-grid-2 ps-mb-6">
            <div className="ps-card ps-card-shine">
              <div className="ps-card-header"><h3 className="ps-card-title">Section-Level Scores</h3></div>
              <div className="ps-card-content ps-space-y-4">
                {result.explanationJson.sections.map(s => (
                  <div key={s.name}>
                    <div className="ps-flex-between ps-mb-1">
                      <span className="ps-text-sm ps-font-medium">{s.name}</span>
                      <span className="ps-text-sm ps-muted-text">{Number(s.score || 0)}/100</span>
                    </div>
                    <div className="ps-progress-track">
                      <div className={`ps-progress-fill ${Number(s.score || 0) < 40 ? 'ps-bg-risk-low' : Number(s.score || 0) < 65 ? 'ps-bg-risk-medium' : 'ps-bg-risk-high'}`} style={{ width: `${Number(s.score || 0)}%` }} />
                    </div>
                    <p className="ps-text-xs ps-muted-text ps-mt-1">{s.detail}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="ps-card ps-card-shine">
              <div className="ps-card-header"><h3 className="ps-card-title">Keywords</h3></div>
              <div className="ps-card-content">
                <div className="ps-flex-wrap ps-gap-2">
                  {result.explanationJson.keywords.map(kw => (
                    <span key={kw} className="ps-badge-secondary">{kw}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}