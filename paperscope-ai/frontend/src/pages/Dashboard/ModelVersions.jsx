import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { Plus, Cpu, CheckCircle2 } from "lucide-react";
import "./Dashboard.css";
import "./AdminDashboard.css";
import "./ModelVersions.css";

export default function ModelVersions() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();

  const [models, setModels] = useState([
    {
      id: 1,
      name: "TF-IDF + LogReg v1.0",
      createdAt: "11/30/2024",
      active: true,
    },
    {
      id: 2,
      name: "TF-IDF + SVM v0.9-beta",
      createdAt: "11/14/2024",
      active: false,
    },
  ]);

  const [toast, setToast] = useState("");

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

  const handleSetActive = (id) => {
    setModels((prev) =>
      prev.map((model) => ({
        ...model,
        active: model.id === id,
      }))
    );

    setToast("Model activated");

    setTimeout(() => {
      setToast("");
    }, 2500);
  };

  const handleAddModel = () => {
    alert("Open add model flow here.");
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
          <Link to="/dashboard/admin/results" className="ps-nav-link">
            🗄️ Results
          </Link>
          <Link to="/dashboard/admin/models" className="ps-nav-link active">
            💠 Models <span className="ps-chevron">›</span>
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
          <div className="model-versions-content">
            <div className="model-versions-header">
              <div>
                <h1>Model Versions</h1>
                <p>Manage ML model versions and artifacts.</p>
              </div>

              <button
                type="button"
                className="add-model-btn"
                onClick={handleAddModel}
              >
                <Plus size={18} />
                <span>Add Model</span>
              </button>
            </div>

            <div className="model-list">
              {models.map((model) => (
                <div className="model-card" key={model.id}>
                  <div className="model-card-left">
                    <div className="model-icon-box">
                      <Cpu size={22} />
                    </div>

                    <div className="model-info">
                      <div className="model-title-row">
                        <h2>{model.name}</h2>

                        {model.active && (
                          <span className="model-active-badge">
                            <CheckCircle2 size={14} />
                            <span>Active</span>
                          </span>
                        )}
                      </div>

                      <p>Created {model.createdAt}</p>
                    </div>
                  </div>

                  <div className="model-card-right">
                    {!model.active && (
                      <button
                        type="button"
                        className="set-active-btn"
                        onClick={() => handleSetActive(model.id)}
                      >
                        Set Active
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {toast && (
            <div className="model-toast">
              <h3>{toast}</h3>
              <p>Active model version updated.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}