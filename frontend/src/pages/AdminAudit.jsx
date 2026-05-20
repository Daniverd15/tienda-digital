import { useEffect, useState } from 'react';
import { Search, Shield, Activity, User, ShoppingBag, Filter, Download } from 'lucide-react';
import api from '../api/client';
import AdminLayout from '../components/AdminLayout';
import { useToast } from '../context/ToastContext';

/**
 * Bitácora de auditoría unificada.
 *
 * Combina dos fuentes:
 *  - Eventos de pedidos: GET /admin/audit-logs (Commerce service)
 *  - Eventos de acceso:  GET /admin/access-logs (Auth service)
 *
 * Cada evento se enriquece con el correlation_id que permite ver "la pelicula
 * completa" de una sesion del usuario (login -> agregar carrito -> checkout ->
 * cambio de estado por admin).
 */

const ACTION_CONFIG = {
  // Order actions
  checkout_started:       { color: '#3b82f6', label: 'Checkout iniciado' },
  payment_approved:       { color: '#1f7a5c', label: 'Pago aprobado' },
  payment_rejected:       { color: '#dc2626', label: 'Pago rechazado' },
  payment_unavailable:    { color: '#f59e0b', label: 'Payment no disponible' },
  payment_pending_or_failed:{ color: '#f59e0b', label: 'Pago pendiente' },
  checkout_no_stock:      { color: '#dc2626', label: 'Sin stock' },
  checkout_reserve_unavailable: { color: '#dc2626', label: 'Inventory no disponible' },
  checkout_reserve_error: { color: '#dc2626', label: 'Error reserva' },
  confirm_after_paid_failed: { color: '#f59e0b', label: 'Confirm post-pago falló' },
  // Auth actions
  login:                  { color: '#1f7a5c', label: 'Inicio de sesión' },
  login_failed:           { color: '#dc2626', label: 'Login fallido' },
  register:               { color: '#3b82f6', label: 'Registro' },
  refresh:                { color: '#8b5cf6', label: 'Token refresh' },
  logout:                 { color: '#9ca3af', label: 'Cierre sesión' },
};

function ActionBadge({ action }) {
  const cfg = ACTION_CONFIG[action] || { color: '#9ca3af', label: action };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', padding: '0.2rem 0.6rem',
      borderRadius: 999, fontSize: '0.72rem', fontWeight: 700,
      background: `${cfg.color}18`, color: cfg.color,
      border: `1px solid ${cfg.color}40`,
    }}>
      {cfg.label}
    </span>
  );
}

function fmtDate(d) {
  if (!d) return '—';
  try { return new Date(d).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }); }
  catch { return '—'; }
}

export default function AdminAudit() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all'); // all | orders | access
  const [days, setDays] = useState(30);
  const [events, setEvents] = useState([]);
  const [orderStats, setOrderStats] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      api.get('/admin/audit-logs').catch(() => ({ data: [] })),
      api.get('/admin/access-logs').catch(() => ({ data: [] })),
      api.get('/admin/orders').catch(() => ({ data: [] })),
    ]).then(([auditR, accessR, ordersR]) => {
      if (!active) return;
      const orderByPK = {};
      (ordersR.data || []).forEach((o) => { orderByPK[o.id] = o; });
      const orderEvents = (auditR.data || []).map((e) => ({
        source: 'order',
        id: `o-${e.id}`,
        action: e.action,
        when: e.created_at,
        actor_id: e.performed_by,
        ref: orderByPK[e.order_id]?.order_code || (e.order_id ? `#${e.order_id}` : ''),
        order_id: e.order_id,
        order_code: orderByPK[e.order_id]?.order_code,
        details: e.details,
        correlation_id: e.correlation_id,
      }));
      const accessEvents = (accessR.data || []).map((e) => ({
        source: 'access',
        id: `a-${e.id}`,
        action: e.action,
        when: e.created_at,
        actor_id: e.user_id,
        ref: e.ip || '—',
        details: e.user_agent,
        correlation_id: e.correlation_id,
      }));
      const all = [...orderEvents, ...accessEvents].sort((a, b) =>
        new Date(b.when) - new Date(a.when));
      setEvents(all);
      // Stats
      const stats = { total: all.length, ordersWithEvents: new Set(orderEvents.map((e) => e.order_id).filter(Boolean)).size };
      stats.loginFailed = accessEvents.filter((e) => e.action === 'login_failed').length;
      stats.paymentApproved = orderEvents.filter((e) => e.action === 'payment_approved').length;
      stats.paymentRejected = orderEvents.filter((e) => e.action === 'payment_rejected').length;
      setOrderStats(stats);
    }).catch(() => {
      toast('Error al cargar la bitácora', 'error');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);  // eslint-disable-line

  const now = Date.now();
  const cutoff = now - (Number(days || 30) * 24 * 60 * 60 * 1000);
  const filtered = events.filter((e) => {
    if (days && new Date(e.when).getTime() < cutoff) return false;
    if (sourceFilter !== 'all' && e.source !== sourceFilter) return false;
    if (actionFilter && e.action !== actionFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (e.action || '').toLowerCase().includes(q)
        || (e.ref || '').toLowerCase().includes(q)
        || (e.correlation_id || '').toLowerCase().includes(q)
        || (e.details || '').toLowerCase().includes(q)
        || String(e.actor_id || '').includes(q);
    }
    return true;
  });

  const actionSet = [...new Set(events.map((e) => e.action))].sort();

  const exportCSV = () => {
    const cell = (v) => `"${String(v ?? '').replaceAll('"', '""')}"`;
    const rows = [
      ['fuente', 'accion', 'fecha', 'usuario_id', 'referencia', 'detalles', 'correlation_id'],
      ...filtered.map((e) => [e.source, e.action, e.when, e.actor_id, e.ref, e.details, e.correlation_id]),
    ];
    const csv = rows.map((r) => r.map(cell).join(';')).join('\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `bitacora_${new Date().toISOString().slice(0,10)}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <AdminLayout><div className="state">Cargando bitácora...</div></AdminLayout>;

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="page-title">Bitácora de auditoría</h1>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary btn-sm" onClick={exportCSV}>
            <Download size={14} /> Exportar CSV
          </button>
        </div>
      </div>

      <div className="alert info" style={{ marginBottom: '1.25rem' }}>
        <Activity size={16} />
        Toda acción crítica del sistema queda registrada para trazabilidad (RNF-14).
        El <strong>correlation_id</strong> permite seguir la pelicula completa de una sesión a
        través de los 5 microservicios (login → checkout → pago → entrega).
      </div>

      {/* KPIs */}
      <div className="kpi-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="kpi-card kpi-blue">
          <div className="kpi-icon"><Activity size={20} /></div>
          <div className="kpi-body">
            <div className="kpi-label">Eventos totales</div>
            <div className="kpi-value">{orderStats.total || 0}</div>
            <div className="kpi-sub">en el periodo cargado</div>
          </div>
        </div>
        <div className="kpi-card kpi-green">
          <div className="kpi-icon"><ShoppingBag size={20} /></div>
          <div className="kpi-body">
            <div className="kpi-label">Pagos aprobados</div>
            <div className="kpi-value">{orderStats.paymentApproved || 0}</div>
            <div className="kpi-sub">Eventos payment_approved</div>
          </div>
        </div>
        <div className="kpi-card kpi-orange">
          <div className="kpi-icon"><Shield size={20} /></div>
          <div className="kpi-body">
            <div className="kpi-label">Pagos rechazados</div>
            <div className="kpi-value">{orderStats.paymentRejected || 0}</div>
            <div className="kpi-sub">Compensaciones SAGA</div>
          </div>
        </div>
        <div className="kpi-card kpi-purple">
          <div className="kpi-icon"><User size={20} /></div>
          <div className="kpi-body">
            <div className="kpi-label">Logins fallidos</div>
            <div className="kpi-value">{orderStats.loginFailed || 0}</div>
            <div className="kpi-sub">Útil para detectar abuso</div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="finance-filter-bar" style={{ marginBottom: '1rem' }}>
        <div className="finance-filter-section">
          <Filter size={14} color="var(--neutral-500)" />
          <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-600)' }}>Origen:</span>
          {[
            { id: 'all',    label: 'Todos' },
            { id: 'order',  label: 'Pedidos' },
            { id: 'access', label: 'Accesos' },
          ].map((s) => (
            <button
              key={s.id}
              className={`filter-chip${sourceFilter === s.id ? ' active' : ''}`}
              onClick={() => setSourceFilter(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <div className="finance-filter-section">
          <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-600)' }}>Periodo:</span>
          {[7, 30, 90, 365].map((d) => (
            <button
              key={d}
              className={`filter-chip${days === d ? ' active' : ''}`}
              onClick={() => setDays(d)}
            >
              Últimos {d} días
            </button>
          ))}
        </div>
      </div>

      <div className="admin-search-bar" style={{ marginBottom: '1.25rem' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
          <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#9ca4a0' }} />
          <input
            value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Código pedido, correlation_id, IP, usuario..."
            style={{ paddingLeft: 36 }}
          />
        </div>
        <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} style={{ width: 'auto', minWidth: 180 }}>
          <option value="">Todas las acciones</option>
          {actionSet.map((a) => <option key={a} value={a}>{ACTION_CONFIG[a]?.label || a}</option>)}
        </select>
        <span style={{ fontSize: '0.8125rem', color: '#9ca4a0' }}>{filtered.length} resultado(s)</span>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Origen</th>
              <th>Acción</th>
              <th>Referencia</th>
              <th>Actor</th>
              <th>Correlation</th>
              <th>Detalle</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={7} className="state">Sin eventos con esos filtros</td></tr>
            ) : (
              filtered.slice(0, 500).map((e) => (
                <tr key={e.id}>
                  <td style={{ fontSize: '0.8125rem', whiteSpace: 'nowrap', color: 'var(--neutral-700)' }}>
                    {fmtDate(e.when)}
                  </td>
                  <td>
                    <span style={{
                      fontSize: '0.7rem', fontWeight: 700,
                      padding: '2px 8px', borderRadius: 99,
                      background: e.source === 'order' ? '#e0f2fe' : '#fef3c7',
                      color: e.source === 'order' ? '#075985' : '#854d0e',
                    }}>
                      {e.source === 'order' ? 'PEDIDO' : 'ACCESO'}
                    </span>
                  </td>
                  <td><ActionBadge action={e.action} /></td>
                  <td style={{ fontSize: '0.8125rem' }}>
                    {e.order_code ? (
                      <span className="font-mono" style={{ fontWeight: 700, color: 'var(--brand-600)' }}>
                        {e.order_code}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--neutral-500)' }}>{e.ref}</span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--neutral-600)' }}>
                    {e.actor_id ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <User size={12} /> #{e.actor_id}
                      </span>
                    ) : <span style={{ color: 'var(--neutral-400)' }}>—</span>}
                  </td>
                  <td>
                    {e.correlation_id ? (
                      <code style={{
                        fontSize: '0.7rem', background: 'var(--neutral-100)',
                        padding: '2px 6px', borderRadius: 4, color: 'var(--neutral-600)',
                      }} title={e.correlation_id}>
                        {String(e.correlation_id).slice(0, 8)}…
                      </code>
                    ) : <span style={{ color: 'var(--neutral-400)' }}>—</span>}
                  </td>
                  <td style={{ maxWidth: 240, fontSize: '0.8125rem', color: 'var(--neutral-600)' }}>
                    {e.details ? (
                      <details>
                        <summary style={{ cursor: 'pointer', fontSize: '0.75rem' }}>Ver detalle</summary>
                        <div style={{ marginTop: 4, fontSize: '0.75rem', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                          {String(e.details).slice(0, 300)}
                        </div>
                      </details>
                    ) : <span style={{ color: 'var(--neutral-400)' }}>—</span>}
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
