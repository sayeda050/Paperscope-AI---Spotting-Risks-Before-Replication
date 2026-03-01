import React, { useMemo, useState } from 'react';
import { Search, AlertTriangle } from 'lucide-react';
import './ErrorLogs.css';

export default function ErrorLogs() {
  const [searchTerm, setSearchTerm] = useState('');

  const logs = [
    {
      id: 1,
      source: 'pdf_extraction',
      timestamp: '1/22/2025, 6:03:00 AM',
      message:
        'PDF extraction failed: corrupted file header at byte offset 1024. PyMuPDF raised fitz.FileDataError.',
      user: 'Alex Rivera',
      paper: 'Statistical Methods for Climate Model Validation',
    },
    {
      id: 2,
      source: 'arxiv_api',
      timestamp: '1/25/2025, 10:30:00 AM',
      message: 'arXiv API rate limit exceeded. Retry after 60s.',
      user: '',
      paper: '',
    },
    {
      id: 3,
      source: 'text_preprocessing',
      timestamp: '2/14/2025, 5:13:00 AM',
      message:
        'NLTK punkt tokenizer not found. Falling back to whitespace tokenization.',
      user: 'Mike Thompson',
      paper: 'Reinforcement Learning in Autonomous Navigation',
    },
    {
      id: 4,
      source: 'model_loader',
      timestamp: '2/15/2025, 3:00:00 AM',
      message: 'Model artifact cache miss for mv2. Reloading from disk.',
      user: '',
      paper: '',
    },
  ];

  const filteredLogs = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();

    if (!term) return logs;

    return logs.filter((log) => {
      return (
        log.source.toLowerCase().includes(term) ||
        log.message.toLowerCase().includes(term) ||
        log.timestamp.toLowerCase().includes(term) ||
        log.user.toLowerCase().includes(term) ||
        log.paper.toLowerCase().includes(term)
      );
    });
  }, [searchTerm]);

  return (
    <div className="error-logs-page">
      <div className="error-logs-topbar">
        <span className="error-logs-role">Admin</span>
      </div>

      <div className="error-logs-content">
        <div className="error-logs-header">
          <h1>Error Logs</h1>
          <p>System error logs for monitoring and debugging.</p>
        </div>

        <div className="error-search-wrap">
          <Search size={18} className="error-search-icon" />
          <input
            type="text"
            placeholder="Search logs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="error-log-list">
          {filteredLogs.length > 0 ? (
            filteredLogs.map((log) => (
              <div className="error-log-card" key={log.id}>
                <div className="error-log-meta">
                  <span className="error-log-tag">{log.source}</span>
                  <span className="error-log-time">{log.timestamp}</span>
                </div>

                <p className="error-log-message">{log.message}</p>

                {(log.user || log.paper) && (
                  <p className="error-log-extra">
                    {log.user && (
                      <>
                        <span className="error-log-label">User:</span> {log.user}
                      </>
                    )}

                    {log.user && log.paper && <span className="error-log-separator"> </span>}

                    {log.paper && (
                      <>
                        <span className="error-log-label">Paper:</span> {log.paper}
                      </>
                    )}
                  </p>
                )}
              </div>
            ))
          ) : (
            <div className="error-empty-state">
              <AlertTriangle size={42} />
              <h3>No matching logs found</h3>
              <p>Try a different keyword to search the logs.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}