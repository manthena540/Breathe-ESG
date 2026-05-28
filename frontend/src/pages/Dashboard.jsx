import { useEffect, useState } from 'react';
import api from '../api';

const SCOPE_COLORS = { '1': '#ef4444', '2': '#f59e0b', '3': '#3b82f6' };
const SCOPE_LABELS = { '1': 'Scope 1 — Direct', '2': 'Scope 2 — Electricity', '3': 'Scope 3 — Value Chain' };
const STATUS_COLORS = {
  pending_review: '#854d0e',
  approved: '#166534',
  rejected: '#991b1b',
  flagged: '#9a3412',
};

function StatCard({ label, value, sub, color }) {
  return (
    <div className="card" style={{ flex: 1, minWidth: 160 }}>
      <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || '#1e293b' }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function BarChart({ data, colorMap, labelMap, valueKey = 'count', labelKey }) {
  if (!data || data.length === 0) return <div style={{ color: '#64748b', fontSize: 13 }}>No data</div>;
  const max = Math.max(...data.map(d => d[valueKey] || 0));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {data.map((d, i) => {
        const key = d[labelKey];
        const label = labelMap?.[key] || key || '—';
        const val = d[valueKey] || 0;
        const pct = max ? (val / max) * 100 : 0;
        const color = colorMap?.[key] || '#16a34a';
        return (
          <div key={i}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
              <span style={{ color: '#1e293b' }}>{label}</span>
              <span style={{ color: '#64748b', fontWeight: 600 }}>{val.toLocaleString()}</span>
            </div>
            <div style={{ height: 8, background: '#f1f5f9', borderRadius: 4 }}>
              <div style={{ height: 8, background: color, borderRadius: 4, width: `${pct}%`, transition: 'width 0.4s' }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Dashboard({ org }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!org) return;
    setLoading(true);
    api.get('/dashboard/summary/', { params: { organization: org.id } })
      .then(r => setSummary(r.data))
      .finally(() => setLoading(false));
  }, [org]);

  if (!org) return <div style={{ color: '#64748b', marginTop: 40, textAlign: 'center' }}>Select an organization to view the dashboard.</div>;
  if (loading) return <div style={{ color: '#64748b', marginTop: 40, textAlign: 'center' }}>Loading…</div>;
  if (!summary) return null;

  const totalCo2 = (summary.total_co2e_kg / 1000).toFixed(1);

  const sourceLabels = { sap: 'SAP (Fuel/Procurement)', utility: 'Utility (Electricity)', travel: 'Corporate Travel' };
  const sourceColors = { sap: '#ef4444', utility: '#f59e0b', travel: '#3b82f6' };

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: '#1e293b' }}>Dashboard</h1>
        <p style={{ color: '#64748b', fontSize: 13 }}>{org.name} — emissions overview</p>
      </div>

      {/* KPI row */}
      <div className="flex gap-4 mb-4" style={{ flexWrap: 'wrap' }}>
        <StatCard label="Total Records" value={summary.total_records.toLocaleString()} />
        <StatCard label="Total CO₂e" value={`${totalCo2} t`} sub="metric tonnes CO₂e" color="#16a34a" />
        <StatCard label="Flagged" value={summary.flagged_count} sub="need analyst review" color="#d97706" />
        <StatCard
          label="Pending Review"
          value={(summary.by_status.find(s => s.status === 'pending_review')?.count || 0)}
          sub="awaiting approval"
          color="#2563eb"
        />
      </div>

      <div className="flex gap-4" style={{ flexWrap: 'wrap', alignItems: 'flex-start' }}>
        {/* Scope breakdown */}
        <div className="card" style={{ flex: '1 1 280px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Records by Scope</h3>
          <BarChart
            data={summary.by_scope}
            colorMap={SCOPE_COLORS}
            labelMap={SCOPE_LABELS}
            labelKey="scope"
          />
          <div style={{ marginTop: 16, borderTop: '1px solid #e2e8f0', paddingTop: 12 }}>
            <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>CO₂e by scope (kg)</div>
            {summary.by_scope.map((s, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: SCOPE_COLORS[s.scope] }}>Scope {s.scope}</span>
                <span style={{ fontWeight: 600 }}>
                  {s.total_co2e ? (+s.total_co2e).toLocaleString(undefined, { maximumFractionDigits: 0 }) + ' kg' : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Status breakdown */}
        <div className="card" style={{ flex: '1 1 240px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Review Status</h3>
          <BarChart
            data={summary.by_status}
            colorMap={STATUS_COLORS}
            labelMap={{ pending_review: 'Pending Review', approved: 'Approved', rejected: 'Rejected', flagged: 'Flagged' }}
            labelKey="status"
          />
        </div>

        {/* Source breakdown */}
        <div className="card" style={{ flex: '1 1 240px' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>By Data Source</h3>
          <BarChart
            data={summary.by_source.map(s => ({ ...s, source: s['ingestion_job__source_type'] }))}
            colorMap={sourceColors}
            labelMap={sourceLabels}
            labelKey="source"
          />
        </div>
      </div>

      <div className="card mt-4" style={{ background: '#f0fdf4', borderColor: '#bbf7d0' }}>
        <div style={{ fontSize: 12, color: '#15803d', fontWeight: 600 }}>How to use this dashboard</div>
        <div style={{ fontSize: 12, color: '#166534', marginTop: 4 }}>
          Go to <strong>Records</strong> to review and approve/reject individual emission rows.
          Upload new data via <strong>Upload</strong>. All approved records are locked for audit.
        </div>
      </div>
    </div>
  );
}
