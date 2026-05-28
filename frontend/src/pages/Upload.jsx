import { useState, useRef } from 'react';
import api from '../api';

const SOURCE_INFO = {
  sap: {
    label: 'SAP — Fuel & Procurement',
    scope: 'Scope 1 (mobile/stationary combustion) & Scope 3 (purchased goods)',
    description: 'SAP flat-file CSV export. Supports German column headers (Buchungsdatum, Werk, Materialgruppe, Menge, Mengeneinheit). Material groups map to fuel types automatically.',
    columns: 'DocumentNumber, Buchungsdatum, Werk, Materialgruppe, Materialbeschreibung, Menge, Mengeneinheit, Nettowert, Waehrung, Lieferant',
  },
  utility: {
    label: 'Utility Portal — Electricity',
    scope: 'Scope 2 (purchased electricity)',
    description: 'CSV export from utility portal. Handles billing periods that don\'t align with calendar months. Emission factor selected by grid region (UK/US/EU/IN).',
    columns: 'Account Number, Meter ID, Site Name, Bill Period Start, Bill Period End, Usage, Unit, Tariff, Cost, Currency, Country, Grid Region',
  },
  travel: {
    label: 'Corporate Travel — Concur/Navan',
    scope: 'Scope 3 (business travel)',
    description: 'Concur Expense Extract format. Handles flights (economy/business/first), hotels (per-night factor), ground transport. Distance estimated from IATA airport codes when not provided.',
    columns: 'Trip ID, Employee ID, Department, Travel Type, Origin Airport, Destination Airport, Departure Date, Return Date, Class, Distance (km), Hotel Name, Nights',
  },
};

export default function Upload({ org }) {
  const [sourceType, setSourceType] = useState('sap');
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef();

  const info = SOURCE_INFO[sourceType];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !org) return;
    setUploading(true);
    setResult(null);
    setError(null);
    const fd = new FormData();
    fd.append('organization', org.id);
    fd.append('source_type', sourceType);
    fd.append('file', file);
    try {
      const r = await api.post('/ingest/', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setResult(r.data);
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
    } catch (err) {
      setError(err.response?.data?.error || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  if (!org) return <div style={{ color: '#64748b', marginTop: 40, textAlign: 'center' }}>Select an organization.</div>;

  return (
    <div style={{ maxWidth: 680 }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Upload Data</h1>
      <p style={{ color: '#64748b', fontSize: 13, marginBottom: 20 }}>Ingest a CSV file from one of the three supported sources.</p>

      <form onSubmit={handleSubmit}>
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 8 }}>Data Source</label>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {Object.entries(SOURCE_INFO).map(([key, s]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSourceType(key)}
                  style={{
                    flex: 1,
                    minWidth: 140,
                    padding: '10px 14px',
                    border: `2px solid ${sourceType === key ? '#16a34a' : '#e2e8f0'}`,
                    borderRadius: 8,
                    background: sourceType === key ? '#f0fdf4' : '#fff',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: sourceType === key ? '#16a34a' : '#1e293b' }}>{s.label}</div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{s.scope}</div>
                </button>
              ))}
            </div>
          </div>

          <div style={{ background: '#f8fafc', borderRadius: 8, padding: 12, marginBottom: 16, fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 4, color: '#1e293b' }}>Expected format</div>
            <div style={{ color: '#64748b', marginBottom: 6 }}>{info.description}</div>
            <div style={{ fontFamily: 'monospace', fontSize: 11, color: '#475569', wordBreak: 'break-word' }}>
              {info.columns}
            </div>
          </div>

          <div>
            <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 8 }}>CSV File</label>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.txt"
              onChange={e => setFile(e.target.files[0])}
              required
              style={{ padding: '6px 0' }}
            />
          </div>
        </div>

        <button type="submit" className="btn-primary" disabled={uploading || !file}>
          {uploading ? 'Uploading…' : 'Upload & Ingest'}
        </button>
      </form>

      {result && (
        <div style={{ marginTop: 20, padding: 16, background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 10 }}>
          <div style={{ fontWeight: 600, color: '#15803d', marginBottom: 8 }}>✓ Ingestion complete</div>
          <div style={{ fontSize: 13, color: '#166534' }}>
            <div>File: {result.original_filename}</div>
            <div>Records loaded: <strong>{result.row_count}</strong></div>
            <div>Errors: <strong>{result.error_count}</strong></div>
          </div>
          {result.error_log?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#854d0e' }}>Parse errors:</div>
              {result.error_log.slice(0, 10).map((e, i) => (
                <div key={i} style={{ fontSize: 11, color: '#92400e', marginTop: 2 }}>• {e}</div>
              ))}
              {result.error_log.length > 10 && (
                <div style={{ fontSize: 11, color: '#92400e' }}>…and {result.error_log.length - 10} more</div>
              )}
            </div>
          )}
          <div style={{ marginTop: 10, fontSize: 12, color: '#15803d' }}>
            Go to <a href="/records">Records</a> to review and approve the imported data.
          </div>
        </div>
      )}

      {error && (
        <div style={{ marginTop: 20, padding: 16, background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 10, color: '#991b1b', fontSize: 13 }}>
          ✕ {error}
        </div>
      )}

      {/* Sample download links */}
      <div className="card mt-4" style={{ fontSize: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Sample files (for testing)</div>
        <div style={{ color: '#64748b' }}>
          Download sample CSVs from the <code>sample_data/</code> directory in the project repo and upload them here to see the pipeline in action.
        </div>
      </div>
    </div>
  );
}
