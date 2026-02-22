import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Shield, FileSearch, Brain, BarChart3, Zap, ArrowRight, Link2, ChevronRight } from 'lucide-react';
import './Index.css';

const features = [
  { icon: <FileSearch size={24} />, title: 'PDF Analysis', desc: 'Upload research papers and get instant AI-powered risk assessments with detailed explanations.' },
  { icon: <Link2 size={24} />, title: 'arXiv Integration', desc: 'Analyze papers directly from arXiv by URL or ID. Metadata auto-fetched for seamless workflows.' },
  { icon: <Brain size={24} />, title: 'ML-Powered Scoring', desc: 'TF-IDF + classifier pipeline scores papers 0-100 with transparent, explainable risk factors.' },
  { icon: <BarChart3 size={24} />, title: 'Explainable Results', desc: 'Keyword analysis, section-level scores, and contributing factors — not just a number.' },
];

const steps = [
  { num: '01', title: 'Upload or Link', desc: 'Submit your paper via PDF upload or arXiv link. Metadata is extracted automatically.' },
  { num: '02', title: 'AI Analysis', desc: 'Our NLP pipeline extracts text, preprocesses it, and runs it through trained classifiers.' },
  { num: '03', title: 'Get Results', desc: 'Receive a detailed risk score, contributing factors, keyword analysis, and actionable insights.' },
];

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5 } }),
};

export default function Index() {
  return (
    <div className="ps-landing-page">
      
      {/* Navbar */}
      <nav className="ps-navbar">
        <div className="ps-container ps-nav-content">
          <Link to="/" className="ps-nav-brand">
            <Shield className="ps-nav-icon" size={24} />
            <span>PaperScope AI</span>
          </Link>
          <div className="ps-nav-actions">
            <Link to="/login" className="ps-btn ps-btn-ghost">Sign In</Link>
            <Link to="/register" className="ps-btn ps-btn-primary">Get Started</Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="ps-hero">
        <div className="ps-container">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            
            <div className="ps-hero-badge">
              <Zap size={14} /> AI-Powered Research Risk Analysis
            </div>
            
            <h1 className="ps-hero-title">
              Spotting Risks <br className="hidden sm:block" />
              <span className="ps-text-gradient">Before Replication</span>
            </h1>
            
            <p className="ps-hero-desc">
              Identify reproducibility risks, methodology gaps, and potential red flags in research papers before you invest in replication.
            </p>
            
            <div className="ps-hero-actions">
              <Link to="/register" className="ps-btn ps-btn-primary ps-btn-lg">
                Start Analyzing <ArrowRight size={18} />
              </Link>
              <Link to="/login" className="ps-btn ps-btn-outline ps-btn-lg">
                Sign In
              </Link>
            </div>
          </motion.div>

          {/* Mock dashboard preview */}
          <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.7 }}>
            <div className="ps-mock-dash">
              <div className="ps-mock-header">
                <div className="ps-dot ps-dot-red" />
                <div className="ps-dot ps-dot-yellow" />
                <div className="ps-dot ps-dot-green" />
                <span className="ps-mock-title">Analysis Dashboard</span>
              </div>
              
              <div className="ps-mock-grid">
                {[
                  { label: 'Papers Analyzed', val: '247' }, 
                  { label: 'Avg Risk Score', val: '42.3' }, 
                  { label: 'High Risk Found', val: '18%' }
                ].map((s) => (
                  <div key={s.label} className="ps-mock-stat">
                    <div className="ps-mock-stat-label">{s.label}</div>
                    <div className="ps-mock-stat-val">{s.val}</div>
                  </div>
                ))}
              </div>
              
              <div className="ps-mock-bar-bg">
                <div className="ps-mock-bar-fill" />
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="ps-section">
        <div className="ps-container">
          <div className="ps-section-header">
            <h2 className="ps-section-title">Powerful Analysis Tools</h2>
            <p className="ps-section-desc">Everything you need to evaluate research reproducibility, powered by machine learning.</p>
          </div>
          
          <div className="ps-features-grid">
            {features.map((f, i) => (
              <motion.div key={f.title} custom={i} variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
                <div className="ps-feature-card">
                  <div className="ps-feature-icon">{f.icon}</div>
                  <h3 className="ps-feature-title">{f.title}</h3>
                  <p className="ps-feature-desc">{f.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works Section */}
      <section className="ps-section ps-section-alt">
        <div className="ps-container">
          <div className="ps-section-header">
            <h2 className="ps-section-title">How It Works</h2>
            <p className="ps-section-desc">Three simple steps from paper submission to actionable risk insights.</p>
          </div>
          
          <div className="ps-steps-grid">
            {steps.map((s, i) => (
              <motion.div key={s.num} custom={i} variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }} className="ps-step">
                <div className="ps-step-num">{s.num}</div>
                <h3 className="ps-step-title">{s.title}</h3>
                <p className="ps-step-desc">{s.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="ps-section">
        <div className="ps-container" style={{ textAlign: 'center' }}>
          <h2 className="ps-section-title">Ready to Evaluate Your Research?</h2>
          <p className="ps-section-desc" style={{ marginBottom: '32px' }}>
            Join researchers using AI to identify reproducibility risks before investing in replication.
          </p>
          <Link to="/register" className="ps-btn ps-btn-primary ps-btn-lg">
            Create Free Account <ChevronRight size={18} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="ps-footer">
        <div className="ps-container ps-footer-content">
          <div className="ps-footer-brand">
            <Shield size={20} className="ps-nav-icon" />
            <span>PaperScope AI</span>
          </div>
          <p className="ps-footer-text">© 2026 PaperScope AI. Built for reproducibility-conscious researchers.</p>
        </div>
      </footer>
      
    </div>
  );
}