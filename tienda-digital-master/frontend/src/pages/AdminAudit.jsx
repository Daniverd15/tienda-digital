/**
 * Pagina de Bitacora de Auditoria (/admin/auditoria).
 *
 * ============================================================================
 * PROPOSITO
 * ============================================================================
 * Unifica DOS fuentes de eventos para que el admin pueda reconstruir la
 * "pelicula" completa de una sesion de usuario:
 *
 *   1. Eventos de PEDIDOS (commerce_db.OrderAuditLog): checkout iniciado,
 *      pago aprobado/rechazado, transiciones de estado, etc.
 *   2. Eventos de ACCESOS (auth_db.AccessLog): login, login_failed, register,
 *      refresh, logout con IP y user_agent.
 *
 * El correlation_id propagado por el gateway permite cruzar eventos de los
 * dos contextos. Click sobre el chip de correlation_id filtra la tabla
 * para mostrar SOLO los eventos de esa sesion.
 *
 * ============================================================================
 * KPIs DESTACADOS
 * ============================================================================
 * - Total de eventos
 * - Pagos aprobados (mes)
 * - Pagos rechazados / compensaciones SAGA
 * - Logins fallidos (util para detectar abuso / brute-force)
 *
 * Soporta exportacion a CSV con BOM UTF-8 para Excel.
 */
import { useEffect, useState } from 'react';
import { Search, Shield, Activity, User, ShoppingBag, Filter, Download, Link2, Copy, MapPin } from 'lucide-react';
import api from '../api/client';
import AdminLayout from '../components/AdminLayout';
import { useToast } from '../context/ToastContext';
import { fmtDateTime, fmtRelative } from '../utils/datetime';

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

export default function AdminAudit() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('all'); // all | orders | access
  const [days, setDays] = useState(30);
  const [events, setEvents] = useState([]);
  const [orderStats, setOrderStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [userMap, setUserMap] = useState({});
  const [expandedCorr, setExpandedCorr] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      api.get('/admin/audit-logs').catch(() => ({ data: [] })),
      api.get('/admin/access-logs').catch(() => ({ data: [] })),
      api.get('/admin/orders').catch(() => ({ data: [] })),
      api.get('/admin/customers').catch(() => ({ data: [] })),
    ]).then(([auditR, accessR, ordersR, customersR]) => {
      if (!active) return;
      // Mapa de usuarios para mostrar nombre real en vez de "#15"
      const uMap = {};
      (customersR.data || []).forEach((c) => { uMap[c.id] = { name: c.name, email: c.email, role: 'customer' }; });
      uMap[1] = uMap[1] || { name: 'Administrador', email: 'admin@tienda.com', role: 'admin' };
      setUserMap(uMap);

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
        order_total: orderByPK[e.order_id]?.total,
        order_user: orderByPK[e.order_id]?.user_id,
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
        ip: e.ip,
        user_agent: e.user_agent,
        details: e.user_agent,
        correlation_id: e.correlation_id,
      }));
      const all = [...orderEvents, ...accessEvents].sort((a, b) =>
        new Date(b.when) - new Date(a.when));
      setEvents(all);
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

  const copyToClipboard = (text) => {
    navigator.clipboard?.writeText(text).then(
      () => toast('Copiado al portapapeles', 'success'),
      () => toast('No se pudo copiar', 'error'),
    );
  };

  const renderActor = (e) => {
    const id = e.actor_id;
    if (!id) {
      if (e.source === 'access' && e.action === 'login_failed') {
        return <span style={{ color: 'var(--error-text)', fontWeight: 600 }}>Email inválido</span>;
      }
      return <span style={{ color: 'var(--neutral-400)' }}>Sistema</span>;
    }
    const u = userMap[id];
    if (u) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ fontWeight: 700, fontSize: '0.8125rem', color: 'var(--neutral-900)' }}>
            {u.role === 'admin' && <Shield size={11} style={{ display: 'inline', marginRight: 3, color: 'var(--brand-600)' }} />}
            {u.name}
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--neutral-500)' }}>{u.email}</span>
        </div>
      );
    }
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--neutral-600)', fontSize: '0.8125rem' }}>
        <User size={12} /> Usuario #{id}
      </span>
    );
  };

  const renderRef = (e) => {
    if (e.source === 'order') {
      if (e.order_code) {
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <span className="font-mono" style={{ fontWeight: 700, color: 'var(--brand-600)', fontSize: '0.8125rem' }}>
              {e.order_code}
            </span>
            {e.order_total && (
              <span style={{ fontSize: '0.7rem', color: 'var(--neutral-500)' }}>
                ${Number(e.order_total).toLocaleString('es-CO')}
              </span>
            )}
          </div>
        );
      }
      return <span style={{ color: 'var(--neutral-500)' }}>{e.ref}</span>;
    }
    // access event: mostrar IP + User-Agent corto
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 600, fontSize: '0.8125rem', color: 'var(--neutral-700)' }}>
          <MapPin size={11} /> {e.ip || '—'}
        </span>
        {e.user_agent && (
          <span style={{ fontSize: '0.7rem', color: 'var(--neutral-500)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                title={e.user_agent}>
            {e.user_agent.includes('Chrome') ? 'Chrome' :
             e.user_agent.includes('Firefox') ? 'Firefox' :
             e.user_agent.includes('Safari') ? 'Safari' :
             e.user_agent.includes('curl') ? 'curl' : 'Navegador'}
          </span>
        )}
      </div>
    );
  };

  const renderCorrelation = (cid) => {
    if (!cid) return <span style={{ color: 'var(--neutral-400)' }}>—</span>;
    const isExpanded = expandedCorr === cid;
    const relatedCount = events.filter((ev) => ev.correlation_id === cid).length;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <button
          type="button"
          onClick={() => setExpandedCorr(isExpanded ? null : cid)}
          title={`Ver ${relatedCount} evento(s) de esta sesión`}
          style={{
            background: isExpanded ? 'var(--brand-100)' : 'var(--neutral-100)',
            border: '1px solid ' + (isExpanded ? 'var(--brand-300)' : 'var(--neutral-200)'),
            padding: '2px 8px', borderRadius: 6, cursor: 'pointer',
            fontSize: '0.7rem', fontFamily: 'monospace',
            color: isExpanded ? 'var(--brand-700)' : 'var(--neutral-700)',
            display: 'inline-flex', alignItems: 'center', gap: 4,
          }}>
          <Link2 size={10} />
          {String(cid).slice(0, 8)}
          {relatedCount > 1 && (
            <span style={{
              background: 'var(--brand-500)', color: '#fff',
              borderRadius: 99, padding: '0 5px', fontSize: '0.65rem', fontWeight: 700,
            }}>
              {relatedCount}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => copyToClipboard(cid)}
          style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--neutral-400)', fontSize: '0.65rem', display: 'inline-flex', alignItems: 'center', gap: 3, padding: 0 }}
          title="Copiar correlation_id">
          <Copy size={9} /> copiar
        </button>
      </div>
    );
  };

  const renderDetail = (e) => {
    if (!e.details && e.action) {
      // Detalle por tipo de acción
      if (e.action === 'payment_approved') return <span style={{ color: 'var(--success-text)', fontWeight: 600 }}>✓ Pago capturado</span>;
      if (e.action === 'payment_rejected') return <span style={{ color: 'var(--error-text)' }}>Compensación SAGA: stock liberado</span>;
      if (e.action === 'login') return <span style={{ color: 'var(--neutral-500)' }}>Sesión iniciada correctamente</span>;
      if (e.action === 'login_failed') return <span style={{ color: 'var(--error-text)' }}>Credenciales incorrectas</span>;
      if (e.action === 'register') return <span style={{ color: 'var(--success-text)' }}>Nueva cuenta creada</span>;
      if (e.action === 'logout') return <span style={{ color: 'var(--neutral-500)' }}>Cierre de sesión local</span>;
      if (e.action === 'refresh') return <span style={{ color: 'var(--neutral-500)' }}>Token renovado</span>;
      return <span style={{ color: 'var(--neutral-400)' }}>—</span>;
    }
    if (!e.details) return <span style={{ color: 'var(--neutral-400)' }}>—</span>;
    const text = String(e.details);
    // Detección de "ref=..." en acciones de pago
    if (text.startsWith('ref=')) {
      return <span style={{ color: 'var(--neutral-600)', fontSize: '0.8rem' }}>
        Ref. pasarela: <code style={{ background: 'var(--neutral-100)', padding: '1px 5px', borderRadius: 3 }}>{text.slice(4)}</code>
      </span>;
    }
    const short = text.length > 120 ? text.slice(0, 117) + '...' : text;
    return (
      <details style={{ fontSize: '0.8rem' }}>
        <summary style={{ cursor: 'pointer', color: 'var(--neutral-700)' }}>{short}</summary>
        {text.length > 120 && (
          <div style={{ marginTop: 6, padding: 8, background: 'var(--neutral-50)', borderRadius: 6, fontFamily: 'monospace', fontSize: '0.72rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {text}
          </div>
        )}
      </details>
    );
  };

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

      {expandedCorr && (
        <div className="alert info" style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>
            Mostrando solo los eventos del correlation <code style={{ background: 'rgba(255,255,255,0.4)', padding: '1px 6px', borderRadius: 4 }}>{expandedCorr.slice(0, 16)}…</code>
          </span>
          <button className="btn btn-ghost btn-sm" onClick={() => setExpandedCorr(null)}>
            Limpiar filtro
          </button>
        </div>
      )}

      <div className="table-wrap">
        <table className="data-table audit-table">
          <thead>
            <tr>
              <th style={{ width: 150 }}>Cuándo</th>
              <th style={{ width: 90 }}>Origen</th>
              <th style={{ width: 160 }}>Acción</th>
              <th style={{ width: 180 }}>Referencia</th>
              <th style={{ width: 200 }}>Actor</th>
              <th style={{ width: 130 }}>Correlation</th>
              <th>Detalle</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={7} className="state">Sin eventos con esos filtros</td></tr>
            ) : (
              filtered
                .filter((e) => !expandedCorr || e.correlation_id === expandedCorr)
                .slice(0, 500)
                .map((e) => (
                <tr key={e.id}>
                  <td style={{ fontSize: '0.8125rem', whiteSpace: 'nowrap' }}>
                    <div style={{ fontWeight: 600, color: 'var(--neutral-800)' }}>{fmtDateTime(e.when)}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--neutral-500)' }}>{fmtRelative(e.when)}</div>
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
                  <td>{renderRef(e)}</td>
                  <td>{renderActor(e)}</td>
                  <td>{renderCorrelation(e.correlation_id)}</td>
                  <td style={{ maxWidth: 320 }}>{renderDetail(e)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}
