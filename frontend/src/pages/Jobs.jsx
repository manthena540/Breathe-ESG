import { useEffect, useState, useCallback } from 'react';
import api from '../api';

const STATUS_STYLE = {
  completed: { color: '#166534', background: '#dcfce7' },
  failed: { color: '#991b1b', background: '#fee2e2' },
  processing: { color: '#1e40af', background: '#dbeafe' },
  pending: { color: '#64748b', background: '#f1f5f9' },
};

export default function Jobs({ org }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(() => {
    if (!org) return;
    setLoading(true);
    api.get('/jobs/', { params: { organization: org.id } })
      .then(r => setJobs(r.data.results || r.data))
      .finally(() => setLoading(false));
  }, [org]);

  useEffect(() => { load(); }, [load]);

  if (!org) return <div style={{ color: '#64748b', marginTop: 40, textAlign: 'center' }}>Select an organization.</div>;

  const sourceLabel = { sap: 'SAP', utility: 'Utility', travel: 'Travel' };

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Ingest Jobs</h1>
        <p style={{ color: '#64748b', fontSize: 13 }}>History of all file uploads and their parse results.</p>
      </div>

      {loading && <div style={{ color: '#64748b', textAlign: 'center', padding: 40 }}>Loading…</div>}

      {!loading && jobs.length === 0 && (
        <div className="card" style={{ textAlign: 'center', color: '#64748b', padding: 40 }}>
          No ingestion jobs yet. Upload a file to get started.
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {jobs.map(j => {
          const s = STATUS_STYLE[j.status] || {};
          return (
            <div key={j.id} className="card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{j.original_filename}</span>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999, ...s }}>
                      {j.status_display}
                    </span>
                    <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase' }}>
                      {sourceLabel[j.source_type] || j.source_type}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: '#64748b' }}>
                    {new Date(j.created_at).toLocaleString()} ·{' '}
                    {j.row_count} records · {j.error_count} errors
                  </div>
                </div>
                {j.error_log?.length > 0 && (
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => setExpanded(expanded === j.id ? null : j.id)}
                  >
                    {expanded === j.id ? 'Hide errors' : `Show ${j.error_log.length} error(s)`}
                  </button>
                )}
              </div>
              {expanded === j.id && j.error_log?.length > 0 && (
                <div style={{ marginTop: 12, background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 6, padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#9a3412', marginBottom: 6 }}>Parse errors</div>
                  {j.error_log.map((e, i) => (
                    <div key={i} style={{ fontSize: 11, color: '#92400e', marginBottom: 2 }}>• {e}</div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
