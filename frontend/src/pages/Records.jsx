import { useEffect, useState, useCallback } from 'react';
import api from '../api';

const STATUS_BADGE = {
  pending_review: 'badge badge-pending',
  approved: 'badge badge-approved',
  rejected: 'badge badge-rejected',
  flagged: 'badge badge-flagged',
};

const SCOPE_BADGE = { '1': 'badge badge-scope1', '2': 'badge badge-scope2', '3': 'badge badge-scope3' };

function FlagList({ flags }) {
  if (!flags || flags.length === 0) return null;
  return (
    <div style={{ marginTop: 4 }}>
      {flags.map((f, i) => (
        <div key={i} style={{ fontSize: 11, color: '#d97706', background: '#fffbeb', padding: '2px 6px', borderRadius: 4, marginBottom: 2 }}>
          ⚠ {f}
        </div>
      ))}
    </div>
  );
}

function ReviewModal({ record, onClose, onSaved }) {
  const [notes, setNotes] = useState(record.review_notes || '');
  const [saving, setSaving] = useState(false);

  const doAction = async (action) => {
    setSaving(true);
    try {
      const r = await api.post(`/records/${record.id}/${action}/`, { notes });
      onSaved(r.data);
      onClose();
    } catch (e) {
      alert(e.response?.data?.error || 'Error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 480, maxWidth: '95vw', maxHeight: '90vh', overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600 }}>Review Record #{record.id}</h3>
          <button className="btn-secondary btn-sm" onClick={onClose}>✕</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 13, marginBottom: 16 }}>
          {[
            ['Source', record.source_type?.toUpperCase()],
            ['Scope', record.scope_display],
            ['Category', record.category_display],
            ['Activity', record.activity_type],
            ['Period', `${record.period_start} → ${record.period_end}`],
            ['Quantity', `${record.quantity} ${record.unit}`],
            ['Normalized', record.quantity_normalized ? `${(+record.quantity_normalized).toFixed(2)} ${record.normalized_unit}` : '—'],
            ['CO₂e', record.co2e_kg ? `${(+record.co2e_kg).toFixed(2)} kg` : '—'],
            ['Facility', record.facility || '—'],
            ['Country', record.country || '—'],
          ].map(([k, v]) => (
            <div key={k}>
              <div style={{ color: '#64748b', fontSize: 11 }}>{k}</div>
              <div style={{ fontWeight: 500 }}>{v || '—'}</div>
            </div>
          ))}
        </div>

        {record.flags?.length > 0 && (
          <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 6, padding: 10, marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#92400e', marginBottom: 6 }}>Flags</div>
            {record.flags.map((f, i) => <div key={i} style={{ fontSize: 12, color: '#92400e' }}>• {f}</div>)}
          </div>
        )}

        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 12, color: '#64748b', display: 'block', marginBottom: 4 }}>Review notes (optional)</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={3}
            placeholder="Add context for the audit trail…"
            disabled={record.is_locked}
          />
        </div>

        {record.is_locked ? (
          <div style={{ textAlign: 'center', color: '#16a34a', fontWeight: 600, fontSize: 13 }}>🔒 Locked for audit</div>
        ) : (
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="btn-warning" onClick={() => doAction('flag')} disabled={saving}>Flag</button>
            <button className="btn-danger" onClick={() => doAction('reject')} disabled={saving}>Reject</button>
            <button className="btn-primary" onClick={() => doAction('approve')} disabled={saving}>Approve</button>
            {record.status === 'approved' && (
              <button className="btn-secondary" onClick={() => doAction('lock')} disabled={saving}>🔒 Lock</button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Records({ org }) {
  const [records, setRecords] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ scope: '', status: '', source_type: '', flagged: '' });
  const [selected, setSelected] = useState(null);

  const load = useCallback(() => {
    if (!org) return;
    setLoading(true);
    const params = { organization: org.id, page, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) };
    api.get('/records/', { params })
      .then(r => {
        setRecords(r.data.results || r.data);
        setCount(r.data.count ?? (r.data.results || r.data).length);
      })
      .finally(() => setLoading(false));
  }, [org, page, filters]);

  useEffect(() => { load(); }, [load]);

  const handleSaved = (updated) => {
    setRecords(recs => recs.map(r => r.id === updated.id ? updated : r));
  };

  if (!org) return <div style={{ color: '#64748b', marginTop: 40, textAlign: 'center' }}>Select an organization.</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>Emission Records</h1>
          <p style={{ color: '#64748b', fontSize: 13 }}>{count} records</p>
        </div>
      </div>

      {/* Filters */}
      <div className="card mb-4" style={{ padding: 12 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <select style={{ width: 'auto' }} value={filters.scope} onChange={e => { setFilters(f => ({ ...f, scope: e.target.value })); setPage(1); }}>
            <option value="">All Scopes</option>
            <option value="1">Scope 1</option>
            <option value="2">Scope 2</option>
            <option value="3">Scope 3</option>
          </select>
          <select style={{ width: 'auto' }} value={filters.status} onChange={e => { setFilters(f => ({ ...f, status: e.target.value })); setPage(1); }}>
            <option value="">All Status</option>
            <option value="pending_review">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="flagged">Flagged</option>
          </select>
          <select style={{ width: 'auto' }} value={filters.source_type} onChange={e => { setFilters(f => ({ ...f, source_type: e.target.value })); setPage(1); }}>
            <option value="">All Sources</option>
            <option value="sap">SAP</option>
            <option value="utility">Utility</option>
            <option value="travel">Travel</option>
          </select>
          <select style={{ width: 'auto' }} value={filters.flagged} onChange={e => { setFilters(f => ({ ...f, flagged: e.target.value })); setPage(1); }}>
            <option value="">All</option>
            <option value="true">Flagged only</option>
          </select>
          <button className="btn-secondary btn-sm" onClick={() => { setFilters({ scope: '', status: '', source_type: '', flagged: '' }); setPage(1); }}>Clear</button>
        </div>
      </div>

      <div className="overflow-auto">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Source</th>
              <th>Scope</th>
              <th>Activity</th>
              <th>Period</th>
              <th>Quantity</th>
              <th>CO₂e (kg)</th>
              <th>Facility</th>
              <th>Status</th>
              <th>Flags</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={11} style={{ textAlign: 'center', color: '#64748b', padding: 32 }}>Loading…</td></tr>
            )}
            {!loading && records.length === 0 && (
              <tr><td colSpan={11} style={{ textAlign: 'center', color: '#64748b', padding: 32 }}>No records found.</td></tr>
            )}
            {records.map(r => (
              <tr key={r.id}>
                <td style={{ color: '#64748b', fontSize: 11 }}>#{r.id}</td>
                <td>
                  <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: '#64748b' }}>
                    {r.source_type}
                  </span>
                </td>
                <td><span className={SCOPE_BADGE[r.scope]}>S{r.scope}</span></td>
                <td style={{ maxWidth: 140 }}>
                  <div style={{ fontWeight: 500 }}>{r.activity_type?.replace(/_/g, ' ')}</div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>{r.category_display}</div>
                </td>
                <td style={{ whiteSpace: 'nowrap', fontSize: 12 }}>
                  {r.period_start}<br /><span style={{ color: '#64748b' }}>{r.period_end}</span>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {(+r.quantity).toLocaleString()} {r.unit}
                </td>
                <td style={{ fontWeight: 500 }}>
                  {r.co2e_kg ? (+r.co2e_kg).toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'}
                </td>
                <td style={{ fontSize: 12, color: '#64748b' }}>{r.facility || '—'}</td>
                <td>
                  <span className={STATUS_BADGE[r.status] || 'badge'}>
                    {r.status_display}
                  </span>
                  {r.is_locked && <span title="Locked for audit" style={{ marginLeft: 4 }}>🔒</span>}
                </td>
                <td>
                  {r.flags?.length > 0 && (
                    <span style={{ color: '#d97706', fontSize: 12 }}>⚠ {r.flags.length}</span>
                  )}
                </td>
                <td>
                  <button className="btn-secondary btn-sm" onClick={() => setSelected(r)}>Review</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', gap: 8, marginTop: 16, alignItems: 'center' }}>
        <button className="btn-secondary btn-sm" onClick={() => setPage(p => p - 1)} disabled={page === 1}>← Prev</button>
        <span style={{ fontSize: 12, color: '#64748b' }}>Page {page} · {count} total</span>
        <button className="btn-secondary btn-sm" onClick={() => setPage(p => p + 1)} disabled={records.length < 50}>Next →</button>
      </div>

      {selected && (
        <ReviewModal record={selected} onClose={() => setSelected(null)} onSaved={handleSaved} />
      )}
    </div>
  );
}
