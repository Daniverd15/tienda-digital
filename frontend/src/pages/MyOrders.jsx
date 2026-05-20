import { Link } from 'react-router-dom';
import { Bell, Package, ShoppingBag, ChevronRight } from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { OrderStatusBadge, PaymentStatusBadge } from '../components/Badge';
import { fmtDate } from '../utils/datetime';

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;

export default function MyOrders() {
  const { data: orders = [], loading, error } = useAsync(async () => {
    const { data } = await api.get('/orders/mine');
    return data;
  }, []);

  if (loading) return <main className="page-shell page-min"><div className="state">Cargando pedidos...</div></main>;
  if (error)   return <main className="page-shell page-min"><div className="state error">{error}</div></main>;

  // KPIs rápidos
  const total = orders.length;
  const delivered = orders.filter((o) => ['ENTREGADO', 'entregado'].includes(o.status)).length;
  const inFlight  = orders.filter((o) => ['PAID', 'EN_PREPARACION', 'ENVIADO', 'pagado', 'preparacion', 'enviado'].includes(o.status)).length;
  const totalSpent = orders
    .filter((o) => ['PAID', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO'].includes(o.status))
    .reduce((s, o) => s + Number(o.total || 0), 0);

  return (
    <main className="page-shell page-min">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Historial</span>
          <h1>Mis pedidos</h1>
        </div>
        <Link to="/notificaciones" className="btn btn-secondary btn-sm">
          <Bell size={15} /> Notificaciones
        </Link>
      </div>

      {orders.length === 0 ? (
        <div className="empty-state-card">
          <ShoppingBag size={56} style={{ color: 'var(--neutral-300)', margin: '0 auto 1rem' }} />
          <div style={{ fontWeight: 700, color: 'var(--neutral-600)', marginBottom: '0.5rem' }}>Sin pedidos aún</div>
          <p style={{ color: 'var(--neutral-400)', marginBottom: '1.5rem' }}>
            Explora el catálogo y realiza tu primera compra. Tu historial aparecerá aquí.
          </p>
          <Link to="/catalogo" className="btn btn-primary">Ver catálogo</Link>
        </div>
      ) : (
        <>
          {/* KPI row */}
          <div className="my-orders-kpis">
            <div className="metric-card">
              <span>Total pedidos</span>
              <strong>{total}</strong>
            </div>
            <div className="metric-card">
              <span>Entregados</span>
              <strong>{delivered}</strong>
            </div>
            <div className="metric-card">
              <span>En camino</span>
              <strong>{inFlight}</strong>
            </div>
            <div className="metric-card">
              <span>Total invertido</span>
              <strong>{COP(totalSpent)}</strong>
            </div>
          </div>

          <div className="orders-list">
            {orders.map((order) => (
              <Link
                key={order.id}
                to={`/pedidos/${order.id}`}
                className="order-row"
              >
                <div className="order-row-icon">
                  <Package size={18} color="var(--brand-500)" />
                </div>
                <div className="order-row-main">
                  <div className="order-code">{order.order_code}</div>
                  <div className="order-date">
                    {fmtDate(order.created_at)} · {order.items?.length || 0} producto(s)
                  </div>
                </div>
                <div className="order-row-status">
                  <OrderStatusBadge status={order.status} />
                  <PaymentStatusBadge status={order.payment_status} />
                </div>
                <div className="order-row-amount">{COP(order.total)}</div>
                <ChevronRight size={18} color="var(--neutral-400)" />
              </Link>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
