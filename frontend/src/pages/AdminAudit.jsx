import { useState } from 'react';
import { Search, Shield } from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import AdminLayout from '../components/AdminLayout';

const ACTION_COLORS = {
  create_employee:    '#3b82f6',
  update_employee:    '#8b5cf6',
  deactivate_employee:'#9ca3af',
  create_expense:     '#f59e0b',
  update_expense:     '#f59e0b',
  delete_expense:     '#ef4444',
  login:              '#22c55e',
  register:           '#22c55e',
  update_profile:     '#3b82f6',
  create_category:    '#1f7a5c',
  update_category:    '#1f7a5c',
  create_product:     '#1f7a5c',
  update_product:     '#1f7a5c',
};

function ActionBadge({ action }) {
  const color = ACTION_COLORS[action] || '#9ca3af';
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '0.2rem 0.55rem',
      borderRadius: 999,
      fontSize: '0.72rem',
      fontWeight: 700,
      background: `${color}18`,
      color,
      border: `1px solid ${color}40`,
    }}>
      {action.replace(/_/g, ' ')}
    </span>
  );
}

export default function AdminAudit() {
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [entityFilter, setEntityFilter] = useState('');

  const { data: audits = [], loading, error } = useAsync(async () => {
    const { data } = await api.get('/admin/audit-logs');
    return data;
  }, []);

  if (loading) return <AdminLayout><div className="state">Cargando bitácora...</div></AdminLayout>;
  if (error)   return <AdminLayout><div className="state error">{error}</div></AdminLayout>;

  const actions  = [...new Set(audits.map((a) => a.action))].sort();
  const entities = [...new Set(audits.map((a) => a.entity))].sort();

  const filtered = audits.filter((a) => {
    if (actionFilter && a.action !== actionFilter) return false;
    if (entityFilter && a.entity !== entityFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        a.action.includes(q) ||
        a.entity.includes(q) ||
        String(a.entity_id).includes(q) ||
        (a.user_id && String(a.user_id).includes(q))
      );
    }
    return true;
  });

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
  };

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">RNF-02</span>
          <h1 className="page-title">Bitácora de auditoría</h1>
        </div>
        <div className="page-actions">
          <span style={{ fontSize: '0.875rem', color: '#677067' }}>{audits.length} registros totales</span>
        </div>
      </div>

      {/* Filters */}
      <div className="admin-search-bar" style={{ marginBottom: '1.25rem' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 320 }}>
          <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#9ca4a0' }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar acción, entidad, ID…"
            style={{ paddingLeft: 36 }}
          />
        </div>
        <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} style={{ width: 'auto', minWidth: 160 }}>
          <option value="">Todas las acciones</option>
          {actions.map((a) => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
        </select>
        <select value={entityFilter} onChange={(e) => setEntityFilter(e.target.value)} style={{ width: 'auto', minWidth: 140 }}>
          <option value="">Todas las entidades</option>
          {entities.map((e) => <option key={e} value={e}>{e}</option>)}
        </select>
        <span style={{ fontSize: '0.8125rem', color: '#9ca4a0' }}>{filtered.length} resultado(s)</span>
      </div>

      {/* Table */}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Acción</th>
              <th>Entidad</th>
              <th>ID entidad</th>
              <th>Usuario</th>
              <th>Fecha</th>
              <th>Detalle</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={7} className="state">Sin registros con ese filtro</td></tr>
            ) : (
              filtered.map((log, i) => (
                <tr key={log.id}>
                  <td style={{ color: '#9ca4a0', fontSize: '0.78rem' }}>#{log.id}</td>
                  <td><ActionBadge action={log.action} /></td>
                  <td style={{ fontWeight: 600, fontSize: '0.875rem' }}>{log.entity}</td>
                  <td className="font-mono" style={{ fontSize: '0.8125rem', color: '#677067' }}>{log.entity_id}</td>
                  <td style={{ fontSize: '0.8125rem', color: '#677067' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Shield size={12} /> #{log.user_id}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: '#9ca4a0', whiteSpace: 'nowrap' }}>
                    {formatDate(log.created_at)}
                  </td>
                  <td style={{ maxWidth: 200 }}>
                    {log.new_value && (
                      <details>
                        <summary style={{ fontSize: '0.75rem', cursor: 'pointer', color: '#677067' }}>Ver datos</summary>
                        <pre style={{ fontSize: '0.7rem', marginTop: 4, color: '#4c5960', whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxWidth: 200 }}>
                          {JSON.stringify(log.new_value, null, 2)}
                        </pre>
                      </details>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}
