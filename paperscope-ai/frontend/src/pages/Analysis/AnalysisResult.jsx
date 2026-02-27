import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from "../../contexts/AuthContext.jsx";
import "./AnalysisResult.css";

// Exact SVGs to match your UI perfectly (No more emojis)
const ShieldIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2dd4bf" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
const DashboardIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>;
const UploadIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>;
const ClockIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>;
const HistoryIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>;
const ProfileIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;
const SignOutIcon = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>;
const ArrowLeft = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="ps-mr-1"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg>;
const TrendingUp = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>;

export default function AnalysisResult() {
  const { jobId } = useParams();
  const { user, logout } = useAuth();

  // Safety check to prevent crashes if user is still loading
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
      <div className="ps-app-frame">
        <main className="ps-main-layout ps-centered">
          <p className="ps-muted-text">Result not found.</p>
          <Link to="/dashboard/jobs" className="ps-btn-outline" style={{marginTop: '16px'}}>
            <ArrowLeft /> Back to Jobs
          </Link>
        </main>
      </div>
    );
  }

  const riskColor = result.riskLabel === 'Low' ? 'ps-text-risk-low' : result.riskLabel === 'Medium' ? 'ps-text-risk-medium' : 'ps-text-risk-high';
  const riskBg = result.riskLabel === 'Low' ? 'ps-bg-risk-low' : result.riskLabel === 'Medium' ? 'ps-bg-risk-medium' : 'ps-bg-risk-high';

  return (
    <div className="ps-app-frame">
      {/* PERFECT SIDEBAR: Matches image_d5a8a4.png perfectly */}
      <aside className="ps-sidebar-dark">
        <div className="ps-brand-section">
          <ShieldIcon />
          <span className="ps-brand-name">PaperScope AI</span>
        </div>
        
        <div className="ps-nav-group">
          <div className="ps-nav-label-caps">NAVIGATION</div>
          <Link to="/dashboard" className="ps-side-link"><DashboardIcon /> Dashboard</Link>
          <Link to="/dashboard/submit" className="ps-side-link"><UploadIcon /> Submit Paper</Link>
          {/* Note: In your picture, this is NOT highlighted as active. I removed the highlight to match. */}
          <Link to="/dashboard/jobs" className="ps-side-link"><ClockIcon /> Analysis Jobs</Link>
          <Link to="/dashboard/history" className="ps-side-link"><HistoryIcon /> History</Link>
          <Link to="/dashboard/profile" className="ps-side-link"><ProfileIcon /> Profile</Link>
        </div>

        <div className="ps-sidebar-bottom">
          <div className="ps-user-pill">
            <div className="ps-user-avatar">
              {user.first_name?.[0] || ""}{user.last_name?.[0] || ""}
            </div>
            <div className="ps-user-info">
              <div className="ps-user-name">{user.first_name} {user.last_name}</div>
              <div className="ps-user-email">{user.email}</div>
            </div>
          </div>
          <button onClick={logout} className="ps-btn-signout">
            <SignOutIcon /> Sign Out
          </button>
        </div>
      </aside>

      <main className="ps-main-layout">
        <div className="ps-top-header">
           <div />
           <div className="ps-role-tag">Researcher</div>
        </div>

        <div className="ps-page-content">
          <div className="ps-mb-6">
            <Link to="/dashboard/jobs" className="ps-btn-ghost ps-mb-4">
              <ArrowLeft /> Back
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
                <h3 className="ps-card-title"><TrendingUp /> Summary</h3>
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