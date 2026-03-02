import React, { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { Upload, Link as LinkIcon, FileText, X } from "lucide-react";
import "./SubmitPaper.css";

export default function SubmitPaper() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState("pdf");
  const [paperTitle, setPaperTitle] = useState("");
  const [arxivLink, setArxivLink] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);

  const fileInputRef = useRef(null);

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const handleFileChange = (file) => {
    if (!file) return;

    if (file.type !== "application/pdf") {
      alert("Only PDF files are allowed.");
      return;
    }

    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      alert("File size must be 50MB or less.");
      return;
    }

    setSelectedFile(file);

    if (!paperTitle.trim()) {
      const nameWithoutExtension = file.name.replace(/\.pdf$/i, "");
      setPaperTitle(nameWithoutExtension);
    }
  };

  const onInputFileChange = (e) => {
    const file = e.target.files?.[0];
    handleFileChange(file);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragActive(false);

    const file = e.dataTransfer.files?.[0];
    handleFileChange(file);
  };

  const removeFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handlePdfSubmit = async (e) => {
    e.preventDefault();

    if (!selectedFile) {
      alert("Please select a PDF file first.");
      return;
    }

    setLoading(true);

    try {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      alert("Paper submitted for analysis successfully.");
    } catch (error) {
      alert("Failed to submit paper.");
    } finally {
      setLoading(false);
    }
  };

  const handleArxivSubmit = async (e) => {
    e.preventDefault();

    if (!arxivLink.trim()) {
      alert("Please enter an arXiv link.");
      return;
    }

    setLoading(true);

    try {
      await new Promise((resolve) => setTimeout(resolve, 1200));
      alert("arXiv paper submitted for analysis successfully.");
    } catch (error) {
      alert("Failed to submit arXiv link.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ps-dashboard-layout">
      <aside className="ps-sidebar">
        <div className="ps-brand">
          <div className="ps-logo-shield">🛡️</div>
          <span className="ps-brand-name">PaperScope AI</span>
        </div>

        <div className="ps-nav-section">
          <p className="ps-nav-label">NAVIGATION</p>

          <Link to="/dashboard" className="ps-nav-link">
            ▦ Dashboard
          </Link>

          <Link to="/dashboard/submit" className="ps-nav-link active">
            ⬆ Submit Paper <span className="ps-chevron">›</span>
          </Link>

          <Link to="/dashboard/jobs" className="ps-nav-link">
            ⏱ Analysis Jobs
          </Link>

          <Link to="/dashboard/history" className="ps-nav-link">
            🕘 History
          </Link>

          <Link to="/dashboard/profile" className="ps-nav-link">
            👤 Profile
          </Link>
        </div>

        <div className="ps-sidebar-footer">
          <div className="ps-user-card">
            <div className="ps-user-avatar">
              {user?.first_name?.[0] || ""}
              {user?.last_name?.[0] || ""}
            </div>
            <div className="ps-user-meta">
              <p className="ps-user-name">
                {user?.first_name} {user?.last_name}
              </p>
              <p className="ps-user-email">{user?.email}</p>
            </div>
          </div>

          <button className="ps-btn-logout" onClick={handleLogout}>
            ⎋ Sign Out
          </button>
        </div>
      </aside>

      <main className="ps-main-content">
        <header className="ps-top-bar">
          <div />
          <span className="ps-role-badge">Researcher</span>
        </header>

        <div className="ps-page-container submit-paper-scope">
          <div className="submit-paper-header">
            <h1>Submit Paper</h1>
            <p>Upload a PDF or provide an arXiv link to start analysis.</p>
          </div>

          <div className="submit-paper-tabs">
            <button
              className={`submit-tab ${activeTab === "pdf" ? "active" : ""}`}
              onClick={() => setActiveTab("pdf")}
              type="button"
            >
              <Upload size={16} />
              <span>Upload PDF</span>
            </button>

            <button
              className={`submit-tab ${activeTab === "arxiv" ? "active" : ""}`}
              onClick={() => setActiveTab("arxiv")}
              type="button"
            >
              <LinkIcon size={16} />
              <span>arXiv Link</span>
            </button>
          </div>

          {activeTab === "pdf" ? (
            <div className="submit-card">
              <h2>Upload Research Paper</h2>
              <p className="submit-card-subtitle">Supported format: PDF (max 50MB)</p>

              <form onSubmit={handlePdfSubmit} className="submit-form">
                <label htmlFor="paperTitle">Paper Title (optional)</label>
                <input
                  id="paperTitle"
                  type="text"
                  placeholder="Auto-detected from PDF if empty"
                  value={paperTitle}
                  onChange={(e) => setPaperTitle(e.target.value)}
                />

                <label>PDF File</label>

                <div
                  className={`upload-dropzone ${dragActive ? "drag-active" : ""}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragActive(true);
                  }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={onDrop}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/pdf"
                    onChange={onInputFileChange}
                    hidden
                  />

                  {!selectedFile ? (
                    <>
                      <FileText className="upload-file-icon" size={52} />
                      <p className="upload-main-text">Click to select or drag & drop</p>
                      <span className="upload-sub-text">PDF files only</span>
                    </>
                  ) : (
                    <div className="selected-file-box">
                      <div className="selected-file-left">
                        <FileText size={22} />
                        <div>
                          <p className="selected-file-name">{selectedFile.name}</p>
                          <span className="selected-file-size">
                            {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                          </span>
                        </div>
                      </div>

                      <button
                        type="button"
                        className="remove-file-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeFile();
                        }}
                      >
                        <X size={18} />
                      </button>
                    </div>
                  )}
                </div>

                <button className="submit-analysis-btn" type="submit" disabled={loading}>
                  <Upload size={16} />
                  <span>{loading ? "Submitting..." : "Submit for Analysis"}</span>
                </button>
              </form>
            </div>
          ) : (
            <div className="submit-card">
              <h2>Submit via arXiv Link</h2>
              <p className="submit-card-subtitle">
                Paste the arXiv abstract or PDF link to analyze the paper
              </p>

              <form onSubmit={handleArxivSubmit} className="submit-form">
                <label htmlFor="arxivLink">arXiv URL</label>
                <input
                  id="arxivLink"
                  type="url"
                  placeholder="https://arxiv.org/abs/1234.56789"
                  value={arxivLink}
                  onChange={(e) => setArxivLink(e.target.value)}
                />

                <button className="submit-analysis-btn" type="submit" disabled={loading}>
                  <LinkIcon size={16} />
                  <span>{loading ? "Submitting..." : "Analyze arXiv Paper"}</span>
                </button>
              </form>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}