import React, { useState } from 'react';
import { Plus, Cpu, CheckCircle2 } from 'lucide-react';
import './ModelVersions.css';

export default function ModelVersions() {
  const [models, setModels] = useState([
    {
      id: 1,
      name: 'TF-IDF + LogReg v1.0',
      createdAt: '11/30/2024',
      active: true,
    },
    {
      id: 2,
      name: 'TF-IDF + SVM v0.9-beta',
      createdAt: '11/14/2024',
      active: false,
    },
  ]);

  const [toast, setToast] = useState('');

  const handleSetActive = (id) => {
    setModels((prev) =>
      prev.map((model) => ({
        ...model,
        active: model.id === id,
      }))
    );

    setToast('Model activated');

    setTimeout(() => {
      setToast('');
    }, 2500);
  };

  const handleAddModel = () => {
    alert('Open add model flow here.');
  };

  return (
    <div className="model-versions-page">
      <div className="model-versions-topbar">
        <span className="model-admin-role">Admin</span>
      </div>

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
  );
}