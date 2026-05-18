import { useState } from 'react';
import { Eye, Search, ShieldOff, ShieldCheck } from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import AdminLayout from '../components/AdminLayout';
import Badge from '../components/Badge';
import Modal from '../components/Modal';
import { OrderStatusBadge, PaymentStatusBadge } from '../components/Badge';
import { useToast } from '../context/ToastContext';

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;

export default function AdminCustomers() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [customers, setCustomers] = useState([]);

  const { loading, error } = useAsync(async () => {
    const { data } = await api.get('/admin/customers');
    setCustomers(data);
    return data;
  }, []);

  const openCustomer = async (customer) => {
    setSelected(customer);
    setLoadingOrders(true);
    try {
      // En microservicios: pedimos /admin/orders filtrado por user_id
      const { data } = await api.get(`/admin/orders?user_id=${customer.id}`);
      setOrders(data);
    } catch {
      toast('Error al cargar los pedidos del cliente.', 'error');
      setOrders([]);
    } finally {
      setLoadingOrders(false);
    }
  };

  const toggleStatus = async (_customer, _active) => {
    // Activar/desactivar clientes no esta implementado en el MVP de microservicios.
    // Auth Service expone GET /admin/customers solo lectura. Quedaria en evolucion futura.
    toast('Activar/desactivar clientes no esta disponible en esta version.', 'warning');
  };

  if (loading) return <AdminLayout><div className="state">Cargando clientes...</div></AdminLayout>;
  if (error)   return <AdminLayout><div className="state error">{error}</div></AdminLayout>;

  const filtered = customers.filter((c) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return c.name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q) || (c.phone || '').includes(q);
  });

  const totalRevenue = orders.reduce((s, o) => s + (o.payment_status === 'aprobado' ? Number(o.total) : 0), 0);

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="page-title">Clientes</h1>
        </div>
        <div className="page-actions">
          <span style={{ fontSize: '0.875rem', color: '#677067' }}>{customers.length} clientes registrados</span>
        </div>
      </div>

      <div className="admin-search-bar">
        <div style={{ position: 'relative', flex: 1, maxWidth: 400 }}>
          <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#9ca4a0' }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nombre, email o teléfono…"
            style={{ paddingLeft: 36 }}
          />
        </div>
        <span style={{ fontSize: '0.8125rem', color: '#9ca4a0' }}>{filtered.length} resultado(s)</span>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Email</th>
              <th>Teléfono</th>
              <th>Estado</th>
              <th style={{ textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={5} className="state">Sin resultados</td></tr>
            ) : (
              filtered.map((c) => (
                <tr key={c.id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <div style={{
                        width: 34, height: 34, borderRadius: '50%',
                        background: c.active ? 'var(--brand-50)' : 'var(--error-bg)',
                        color: c.active ? 'var(--brand-600)' : 'var(--error-text)',
                        display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: '0.8125rem', flexShrink: 0,
                      }}>
                        {c.name.charAt(0).toUpperCase()}
                      </div>
                      <strong style={{ fontSize: '0.875rem' }}>{c.name}</strong>
                    </div>
                  </td>
                  <td style={{ fontSize: '0.875rem', color: '#677067' }}>{c.email}</td>
                  <td style={{ fontSize: '0.875rem', color: '#677067' }}>{c.phone || '—'}</td>
                  <td>
                    <Badge variant={c.active ? 'success' : 'error'}>
                      {c.active ? 'Activo' : 'Restringido'}
                    </Badge>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div className="table-actions" style={{ justifyContent: 'flex-end' }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => openCustomer(c)} title="Ver pedidos">
                        <Eye size={14} /> Ver pedidos
                      </button>
                      {c.active ? (
                        <button
                          className="btn btn-danger btn-sm btn-icon"
                          onClick={() => toggleStatus(c, false)}
                          title="Restringir cliente"
                        >
                          <ShieldOff size={14} />
                        </button>
                      ) : (
                        <button
                          className="btn btn-secondary btn-sm btn-icon"
                          onClick={() => toggleStatus(c, true)}
                          title="Activar cliente"
                        >
                          <ShieldCheck size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Modal
        open={!!selected}
        onClose={() => { setSelected(null); setOrders([]); }}
        title={selected?.name}
        size="lg"
        footer={
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            {selected && (
              selected.active ? (
                <button className="btn btn-danger btn-sm" onClick={() => toggleStatus(selected, false)}>
                  <ShieldOff size={14} /> Restringir
                </button>
              ) : (
                <button className="btn btn-secondary btn-sm" onClick={() => toggleStatus(selected, true)}>
                  <ShieldCheck size={14} /> Activar
                </button>
              )
            )}
            <button className="btn btn-secondary" onClick={() => { setSelected(null); setOrders([]); }}>Cerrar</button>
          </div>
        }
      >
        {selected && (
          <div style={{ display: 'grid', gap: '1.25rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              {[
                ['Email', selected.email],
                ['Teléfono', selected.phone || '—'],
                ['Estado', <Badge key="s" variant={selected.active ? 'success' : 'error'}>{selected.active ? 'Activo' : 'Restringido'}</Badge>],
                ['Pedidos', orders.length],
                ['Ventas aprobadas', COP(totalRevenue)],
              ].map(([k, v]) => (
                <div key={k} style={{ background: '#f8f9f7', borderRadius: 10, padding: '0.75rem' }}>
                  <div style={{ fontSize: '0.75rem', color: '#9ca4a0', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{k}</div>
                  <div style={{ fontWeight: 700, color: '#172026', marginTop: 2 }}>{v}</div>
                </div>
              ))}
            </div>

            <div>
              <div style={{ fontWeight: 700, marginBottom: '0.75rem', fontSize: '0.9375rem' }}>Historial de pedidos</div>
              {loadingOrders ? (
                <div className="state">Cargando pedidos...</div>
              ) : orders.length === 0 ? (
                <div className="state">Sin pedidos registrados</div>
              ) : (
                <table className="data-table">
                  <thead><tr><th>Código</th><th>Estado</th><th>Pago</th><th style={{textAlign:'right'}}>Total</th></tr></thead>
                  <tbody>
                    {orders.map((o) => (
                      <tr key={o.id}>
                        <td className="font-mono" style={{ fontWeight: 700, fontSize: '0.8125rem' }}>{o.order_code}</td>
                        <td><OrderStatusBadge status={o.status} /></td>
                        <td><PaymentStatusBadge status={o.payment_status} /></td>
                        <td style={{ textAlign: 'right', fontWeight: 700 }}>{COP(o.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </Modal>
    </AdminLayout>
  );
}
