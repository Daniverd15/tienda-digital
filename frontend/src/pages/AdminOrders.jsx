import { useState } from 'react';
import { Search, RefreshCw, Eye } from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import AdminLayout from '../components/AdminLayout';
import { OrderStatusBadge, PaymentStatusBadge } from '../components/Badge';
import Modal from '../components/Modal';
import { useToast } from '../context/ToastContext';

/**
 * Solo mostramos en el panel admin pedidos que se materializaron como ventas
 * operativas. PAGO_RECHAZADO, PAGO_PENDIENTE y SIN_STOCK son artefactos de la
 * SAGA (errores en el checkout) y no representan ventas reales — quedan
 * disponibles para auditoria en la bitacora pero no requieren accion del
 * admin sobre el pedido.
 */
const FILTERS = [
  { id: 'todos',          label: 'Todos' },
  { id: 'pagado',         label: 'Pagado',          statuses: ['PAID'] },
  { id: 'preparacion',    label: 'En preparación',  statuses: ['EN_PREPARACION'] },
  { id: 'enviado',        label: 'Enviado',         statuses: ['ENVIADO'] },
  { id: 'entregado',      label: 'Entregado',       statuses: ['ENTREGADO'] },
  { id: 'cancelado',      label: 'Cancelado',       statuses: ['CANCELADA'] },
];

const OPERATIONAL_STATUSES = new Set(['PAID', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO', 'CANCELADA']);

const STATUS_OPTIONS = {
  PAID: ['EN_PREPARACION', 'CANCELADA'],
  EN_PREPARACION: ['ENVIADO', 'CANCELADA'],
  ENVIADO: ['ENTREGADO'],
};

const STATUS_LABELS = {
  PAID: 'Pagado',
  EN_PREPARACION: 'En preparación',
  ENVIADO: 'Enviado',
  ENTREGADO: 'Entregado',
  CANCELADA: 'Cancelado',
};

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;

const labelStatus = (status) => STATUS_LABELS[status] || String(status || '').replace('_', ' ').toLowerCase();

const matchesFilter = (order, filter) => {
  if (filter.id === 'todos') return true;
  return (filter.statuses || []).includes(order.status)
    || (filter.paymentStatuses || []).includes(order.payment_status);
};

const transitionOptions = (status) => STATUS_OPTIONS[status] || [];

export default function AdminOrders() {
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState('todos');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);

  const { data: orders = [], loading, error, setData, refetch } = useAsync(async () => {
    const { data } = await api.get('/admin/orders');
    // Solo mostramos pedidos con estados "operativos" en el panel admin.
    // Los rechazados / pendientes / sin stock siguen registrados en DB y se
    // consultan via la bitacora de auditoria, no en este listado.
    return (data || []).filter((o) => OPERATIONAL_STATUSES.has(o.status));
  }, []);

  const updateStatus = async (order, status) => {
    try {
      await api.patch(`/admin/orders/${order.id}/status`, { new_status: status });
      // Recargamos el pedido completo desde el servidor
      const { data: refreshed } = await api.get(`/admin/orders/${order.id}`);
      setData(orders.map((o) => (o.id === order.id ? refreshed : o)));
      if (selected?.id === order.id) setSelected(refreshed);
      toast(`Pedido actualizado a "${labelStatus(status)}".`, 'success');
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al actualizar estado.', 'error');
    }
  };

  if (loading) return <AdminLayout><div className="state">Cargando pedidos...</div></AdminLayout>;
  if (error)   return <AdminLayout><div className="state error">{error}</div></AdminLayout>;

  const filtered = orders.filter((o) => {
    const filter = FILTERS.find((f) => f.id === statusFilter) || FILTERS[0];
    const matchStatus = matchesFilter(o, filter);
    const matchSearch = !search || o.order_code.toLowerCase().includes(search.toLowerCase()) || (o.contact_email || '').toLowerCase().includes(search.toLowerCase());
    return matchStatus && matchSearch;
  });

  const counts = FILTERS.reduce((acc, filter) => {
    acc[filter.id] = orders.filter((o) => matchesFilter(o, filter)).length;
    return acc;
  }, {});

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="page-title">Gestión de pedidos</h1>
        </div>
        <div className="page-actions">
          <span style={{ fontSize: '0.875rem', color: '#677067' }}>{orders.length} pedidos totales</span>
        </div>
      </div>

      {/* Status filter chips */}
      <div className="filter-row" style={{ marginBottom: '1rem' }}>
        {FILTERS.map((filter) => (
          <button
            key={filter.id}
            className={`filter-chip${statusFilter === filter.id ? ' active' : ''}`}
            onClick={() => setStatusFilter(filter.id)}
          >
            {filter.label}
            {counts[filter.id] > 0 && (
              <span style={{
                background: statusFilter === filter.id ? 'rgba(255,255,255,0.3)' : 'var(--neutral-200)',
                color: statusFilter === filter.id ? '#fff' : 'var(--neutral-600)',
                borderRadius: 99,
                fontSize: '0.7rem',
                padding: '0px 6px',
                fontWeight: 800,
              }}>
                {counts[filter.id]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Search bar */}
      <div className="admin-search-bar" style={{ marginBottom: '1.25rem' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
          <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#9ca4a0' }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por código o email…"
            style={{ paddingLeft: 36 }}
          />
        </div>
        <span style={{ fontSize: '0.8125rem', color: '#9ca4a0' }}>{filtered.length} resultado(s)</span>
      </div>

      {/* Table */}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Estado pedido</th>
              <th>Estado pago</th>
              <th>Total</th>
              <th>Dirección entrega</th>
              <th>Cambiar estado</th>
              <th style={{ textAlign: 'right' }}>Ver</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={7} className="state">Sin pedidos con ese filtro</td></tr>
            ) : (
              filtered.map((order) => (
                <tr key={order.id}>
                  <td><span className="font-mono" style={{ fontWeight: 800, fontSize: '0.875rem' }}>{order.order_code}</span></td>
                  <td><OrderStatusBadge status={order.status} /></td>
                  <td><PaymentStatusBadge status={order.payment_status} /></td>
                  <td style={{ fontWeight: 700 }}>{COP(order.total)}</td>
                  <td style={{ fontSize: '0.8125rem', color: '#677067', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {order.delivery_city || '—'}
                  </td>
                  <td>
                    {transitionOptions(order.status).length > 0 ? (
                      <select
                        value={order.status}
                        onChange={(e) => updateStatus(order, e.target.value)}
                        style={{ width: 'auto', fontSize: '0.8125rem', padding: '0.4rem 0.6rem' }}
                      >
                        <option value={order.status}>{labelStatus(order.status)}</option>
                        {transitionOptions(order.status).map((s) => (
                          <option key={s} value={s}>{labelStatus(s)}</option>
                        ))}
                      </select>
                    ) : (
                      <span style={{ color: 'var(--neutral-400)', fontSize: '0.8125rem' }}>Sin cambios</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn btn-ghost btn-sm btn-icon" onClick={() => setSelected(order)} title="Ver detalle">
                      <Eye size={15} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Detail modal */}
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title={`Pedido ${selected?.order_code}`}
        size="lg"
        footer={
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <label style={{ margin: 0, fontWeight: 700, fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: 8 }}>
              Estado:
              {selected && transitionOptions(selected.status).length > 0 ? (
                <select
                  value={selected.status}
                  onChange={(e) => updateStatus(selected, e.target.value)}
                  style={{ width: 'auto', fontWeight: 700 }}
                >
                  <option value={selected.status}>{labelStatus(selected.status)}</option>
                  {transitionOptions(selected.status).map((s) => <option key={s} value={s}>{labelStatus(s)}</option>)}
                </select>
              ) : (
                <span style={{ color: 'var(--neutral-500)' }}>{labelStatus(selected?.status)}</span>
              )}
            </label>
            <button className="btn btn-secondary" onClick={() => setSelected(null)}>Cerrar</button>
          </div>
        }
      >
        {selected && (
          <div style={{ display: 'grid', gap: '1.25rem' }}>
            {/* Summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '0.75rem' }}>
              {[
                ['Subtotal', COP(selected.subtotal)],
                ['Adicionales', COP(selected.additional_costs)],
                ['Descuento', COP(selected.discount)],
                ['Total', COP(selected.total)],
                ['Pago', selected.payment_status],
                ['Estado', selected.status],
              ].map(([k, v]) => (
                <div key={k} style={{ background: '#f8f9f7', borderRadius: 10, padding: '0.75rem' }}>
                  <div style={{ fontSize: '0.75rem', color: '#9ca4a0', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{k}</div>
                  <div style={{ fontWeight: 800, fontSize: '1rem', color: '#172026', marginTop: 2 }}>{v}</div>
                </div>
              ))}
            </div>

            {/* Delivery info */}
            <div style={{ background: '#f8f9f7', borderRadius: 10, padding: '1rem' }}>
              <div style={{ fontWeight: 700, marginBottom: '0.5rem' }}>Datos de entrega</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem 1rem', fontSize: '0.875rem' }}>
                <span><strong>Nombre:</strong> {selected.delivery_name}</span>
                <span><strong>Ciudad:</strong> {selected.delivery_city}</span>
                <span><strong>Dirección:</strong> {selected.delivery_address}</span>
                <span><strong>Teléfono:</strong> {selected.contact_phone}</span>
                <span><strong>Email:</strong> {selected.contact_email}</span>
                <span><strong>Doc. facturación:</strong> {selected.billing_document}</span>
              </div>
            </div>

            {/* Items */}
            {selected.items?.length > 0 && (
              <div>
                <div style={{ fontWeight: 700, marginBottom: '0.5rem' }}>Artículos</div>
                <table className="data-table" style={{ fontSize: '0.875rem' }}>
                  <thead><tr><th>Producto</th><th>Variante</th><th>Cant.</th><th style={{textAlign:'right'}}>Total</th></tr></thead>
                  <tbody>
                    {selected.items.map((item) => (
                      <tr key={item.id}>
                        <td><strong>{item.product_name}</strong></td>
                        <td style={{ color: '#677067' }}>{item.variant_description || '—'}</td>
                        <td>{item.quantity}</td>
                        <td style={{ textAlign: 'right', fontWeight: 700 }}>{COP(item.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Modal>
    </AdminLayout>
  );
}
