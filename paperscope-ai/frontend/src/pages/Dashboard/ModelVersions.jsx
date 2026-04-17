import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext.jsx";
import { CheckCircle2, Cpu, Plus } from "lucide-react";
import "./Dashboard.css";
import "./AdminDashboard.css";
import "./ModelVersions.css";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  `http://${window.location.hostname}:8000`;

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return "";
}

function getStoredAuthToken() {
  const possibleKeys = [
    "token",
    "accessToken",
    "access_token",
    "authToken",
    "auth_token",
    "key",
  ];

  for (const key of possibleKeys) {
    const localValue = window.localStorage.getItem(key);
    if (localValue) return localValue;

    const sessionValue = window.sessionStorage.getItem(key);
    if (sessionValue) return sessionValue;
  }

  return "";
}

async function apiRequest(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const csrftoken = getCookie("csrftoken");
  const token = getStoredAuthToken();

  const headers = {
    ...(options.headers || {}),
  };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (token && !headers.Authorization) {
    headers.Authorization =
      token.startsWith("Token ") || token.startsWith("Bearer ")
        ? token
        : `Token ${token}`;
  }

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && csrftoken) {
    headers["X-CSRFToken"] = csrftoken;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      (typeof data === "object" && data?.detail) ||
      (typeof data === "object" && data?.message) ||
      (typeof data === "string" && data) ||
      `Request failed with status ${response.status}.`;
    throw new Error(message);
  }

  return data;
}

function formatAccuracy(value) {
  if (value === null || value === undefined || value === "") return "";

  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "";

  const pct = numeric <= 1 ? numeric * 100 : numeric;
  return `${pct.toFixed(2)}%`;
}

function pickFirst(...values) {
  for (const value of values) {
    if (value !== null && value !== undefined && value !== "") {
      return value;
    }
  }
  return null;
}

function normalizeModel(model) {
  const metrics =
    model?.metrics && typeof model.metrics === "object" ? model.metrics : {};
  const metadata =
    model?.metadata && typeof model.metadata === "object" ? model.metadata : {};

  const id = pickFirst(model?.id, model?.model_id, model?.model_key, model?.pk);
  const name = pickFirst(
    model?.name,
    model?.display_name,
    model?.model_name,
    metadata?.display_name,
    metadata?.model_name,
    id,
    "Unnamed model"
  );
  const active = Boolean(
    model?.active ?? model?.is_active ?? model?.active_flag ?? false
  );
  const createdAt = pickFirst(
    model?.createdAt,
    model?.created_at,
    model?.trained_at,
    metadata?.created_at,
    metadata?.trained_at,
    model?.run_id,
    metadata?.run_id,
    "Unknown"
  );
  const modelType = pickFirst(
    model?.modelType,
    model?.model_type,
    [metadata?.vectorizer_type, metadata?.classifier_type]
      .filter(Boolean)
      .join(" + "),
    metadata?.model_name,
    ""
  );
  const testAccuracy = pickFirst(
    metrics?.testAccuracy,
    metrics?.test_accuracy,
    model?.test_accuracy,
    metadata?.test_accuracy,
    metadata?.accuracy,
    null
  );
  const status = pickFirst(
    model?.status,
    model?.score_calibrator_path ? "Calibrated" : "Ready",
    "Ready"
  );

  return {
    ...model,
    id,
    name,
    active,
    createdAt,
    modelType,
    metrics: {
      ...metrics,
      testAccuracy,
    },
    status,
  };
}

export default function ModelVersions() {
  const { user, logout, initializing } = useAuth();
  const navigate = useNavigate();

  const [models, setModels] = useState([]);
  const [toast, setToast] = useState("");
  const [loadingModels, setLoadingModels] = useState(true);
  const [busyModelId, setBusyModelId] = useState(null);
  const [pageError, setPageError] = useState("");

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
    if (!initializing && user && (user.is_superuser || user.role === "ADMIN")) {
      loadModels();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initializing, user]);

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

  async function loadModels() {
    setLoadingModels(true);
    setPageError("");

    try {
      const data = await apiRequest("/api/analysis/models/");
      const rawModels = Array.isArray(data?.models)
        ? data.models
        : Array.isArray(data)
        ? data
        : [];
      setModels(rawModels.map(normalizeModel).filter((model) => model.id));
    } catch (err) {
      setModels([]);
      setPageError(err.message || "Failed to load models.");
    } finally {
      setLoadingModels(false);
    }
  }

  const handleSetActive = async (id) => {
    setBusyModelId(id);
    setPageError("");

    try {
      await apiRequest("/api/analysis/models/activate/", {
        method: "POST",
        body: JSON.stringify({ model_id: id }),
      });

      await loadModels();

      setToast("Model activated");
      window.setTimeout(() => setToast(""), 2500);
    } catch (err) {
      setPageError(err.message || "Failed to activate model.");
    } finally {
      setBusyModelId(null);
    }
  };

  const handleAddModel = async () => {
    setPageError("");

    try {
      await apiRequest("/api/analysis/models/refresh/", {
        method: "POST",
        body: JSON.stringify({}),
      });

      await loadModels();

      setToast("Model registry refreshed");
      window.setTimeout(() => setToast(""), 2500);
    } catch (err) {
      setPageError(err.message || "Failed to refresh model registry.");
    }
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

            {pageError && (
              <div
                style={{
                  marginBottom: "16px",
                  padding: "12px 14px",
                  borderRadius: "10px",
                  background: "#fef2f2",
                  color: "#991b1b",
                  border: "1px solid #fecaca",
                }}
              >
                {pageError}
              </div>
            )}

            {loadingModels ? (
              <div className="model-card">
                <div className="model-card-left">
                  <div className="model-icon-box">
                    <Cpu size={22} />
                  </div>
                  <div className="model-info">
                    <div className="model-title-row">
                      <h2>Loading models...</h2>
                    </div>
                    <p>Please wait.</p>
                  </div>
                </div>
              </div>
            ) : models.length === 0 ? (
              <div className="model-card">
                <div className="model-card-left">
                  <div className="model-icon-box">
                    <Cpu size={22} />
                  </div>
                  <div className="model-info">
                    <div className="model-title-row">
                      <h2>No models found</h2>
                    </div>
                    <p>
                      Put each model inside backend/ml_assets/models in its own folder
                      with both vectorizer.joblib and classifier.joblib, then press Add
                      Model.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
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

                        <p>
                          Created {model.createdAt}
                          {model.modelType ? ` • ${model.modelType}` : ""}
                          {model.metrics?.testAccuracy !== null &&
                          model.metrics?.testAccuracy !== undefined
                            ? ` • Test Acc ${formatAccuracy(model.metrics.testAccuracy)}`
                            : ""}
                          {model.status ? ` • ${model.status}` : ""}
                        </p>
                      </div>
                    </div>

                    <div className="model-card-right">
                      {!model.active && (
                        <button
                          type="button"
                          className="set-active-btn"
                          onClick={() => handleSetActive(model.id)}
                          disabled={busyModelId === model.id}
                        >
                          {busyModelId === model.id ? "Activating..." : "Set Active"}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
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