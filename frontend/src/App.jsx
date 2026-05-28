import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Records from './pages/Records';
import Jobs from './pages/Jobs';
import api from './api';

function App() {
  const [org, setOrg] = useState(null);
  const [orgs, setOrgs] = useState([]);

  useEffect(() => {
    api.get('/organizations/').then(r => {
      setOrgs(r.data.results || r.data);
      if ((r.data.results || r.data).length > 0) setOrg((r.data.results || r.data)[0]);
    }).catch(err => {
      console.error('API error:', err?.message, err?.response?.status, err?.code);
    });
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <nav style={{
        background: '#fff',
        borderBottom: '1px solid #e2e8f0',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 24,
        height: 52,
        position: 'sticky', top: 0, zIndex: 100,
      }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: '#16a34a', marginRight: 8 }}>
          🌱 Breathe ESG
        </span>
        {[
          { to: '/', label: 'Dashboard' },
          { to: '/records', label: 'Records' },
          { to: '/upload', label: 'Upload' },
          { to: '/jobs', label: 'Ingest Jobs' },
        ].map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              color: isActive ? '#16a34a' : '#64748b',
              fontWeight: isActive ? 600 : 400,
              fontSize: 13,
              textDecoration: 'none',
              borderBottom: isActive ? '2px solid #16a34a' : '2px solid transparent',
              paddingBottom: 2,
            })}
          >
            {label}
          </NavLink>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: '#64748b' }}>Org:</span>
          <select
            value={org?.id || ''}
            onChange={e => setOrg(orgs.find(o => o.id === +e.target.value))}
            style={{ fontSize: 12, padding: '3px 6px', width: 'auto' }}
          >
            {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </div>
      </nav>
      <main style={{ flex: 1, padding: '24px', maxWidth: 1280, margin: '0 auto', width: '100%' }}>
        <Routes>
          <Route path="/" element={<Dashboard org={org} />} />
          <Route path="/records" element={<Records org={org} />} />
          <Route path="/upload" element={<Upload org={org} />} />
          <Route path="/jobs" element={<Jobs org={org} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
