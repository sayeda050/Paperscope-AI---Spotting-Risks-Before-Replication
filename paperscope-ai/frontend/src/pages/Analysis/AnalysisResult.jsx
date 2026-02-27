import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import "./AnalysisResult.css";

// Icons matching AnalysisJobs for consistency
const RefreshCw = () => <span>🔄</span>;
const Eye = () => <span>👁️</span>;

export default function AnalysisResult() {
  const { jobId } = useParams();
  const { user, logout } = useAuth();

  if (!user) return null;

  const mockResults = [
    {
      jobId: 'j1',
      paperTitle: 'Deep Learning for Protein Folding: A Reproducibility Study',
      completedAt: '2025-01-10T15:05:00Z',
      riskScore: 72,
      riskLabel: 'High',
      explanationJson: {
        summary: 'This paper presents significant reproducibility risks due to missing dataset availability, lack of statistical rigor in reported results, and insufficient documentation of hyperparameter optimization.',
        topFactors: [
          'Missing dataset availability statement',
          'No confidence intervals reported',
          'Single random seed used',
          'Hyperparameter search not documented'
        ],
        sections: [
          { name: 'Methodology', score: 65, detail: 'Methods described at high level but lack implementation specifics' },
          { name: 'Data Availability', score: 82, detail: 'No data sharing statement; proprietary dataset mentioned' },
          { name: 'Statistical Rigor', score: 78, detail: 'Results reported without confidence intervals or variance' },
          { name: 'Code Availability', score: 60, detail: 'GitHub link provided but repository is empty' }
        ],
        keywords: ['deep learning', 'protein folding', 'reproducibility', 'neural network', 'benchmark']
      }
    }
  ];

  const result = mockResults.find(r => r.jobId === jobId);

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
      {/* Sidebar - EXACT MATCH to AnalysisJobs.jsx */}
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
            <p className="ps-view-subtitle">Analysis completed {new Date(result.completedAt).toLocaleString()}</p>
          </div>

          <div className="ps-grid-3 ps-mb-6">
            <div className="ps-card ps-card-shine ps-col-1 ps-text-center ps-p-6">
              <p className="ps-text-sm ps-muted-text ps-mb-2">Risk Score</p>
              <p className={`ps-text-6xl ps-font-extrabold ${riskColor}`}>{result.riskScore}</p>
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
                      <span className="ps-text-sm ps-muted-text">{s.score}/100</span>
                    </div>
                    <div className="ps-progress-track">
                      <div className={`ps-progress-fill ${s.score < 40 ? 'ps-bg-risk-low' : s.score < 65 ? 'ps-bg-risk-medium' : 'ps-bg-risk-high'}`} style={{ width: `${s.score}%` }} />
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