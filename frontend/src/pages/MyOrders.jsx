import { Link } from 'react-router-dom';
import { Bell, Package, ShoppingBag } from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { OrderStatusBadge, PaymentStatusBadge } from '../components/Badge';

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;

export default function MyOrders() {
  const { data: orders = [], loading, error } = useAsync(async () => {
    const { data } = await api.get('/orders/mine');
    return data;
  }, []);

  if (loading) return <div className="state">Cargando pedidos...</div>;
  if (error)   return <div className="state error">{error}</div>;

  return (
    <main className="page-shell">
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
        <div style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <ShoppingBag size={56} style={{ color: 'var(--neutral-300)', margin: '0 auto 1rem' }} />
          <div style={{ fontWeight: 700, color: 'var(--neutral-600)', marginBottom: '0.5rem' }}>Sin pedidos aún</div>
          <p style={{ color: 'var(--neutral-400)', marginBottom: '1.5rem' }}>Explora el catálogo y realiza tu primera compra.</p>
          <Link to="/catalogo" className="btn btn-primary">Ver catálogo</Link>
        </div>
      ) : (
        <div>
          {orders.map((order) => (
            <Link
              key={order.id}
              to={`/pedidos/${order.id}`}
              className="order-card"
            >
              <div>
                <Package size={18} color="var(--brand-500)" />
              </div>
              <div>
                <div className="order-code">{order.order_code}</div>
                <div className="order-date" style={{ marginTop: 2 }}>
                  {order.created_at ? new Date(order.created_at).toLocaleDateString('es-CO', { dateStyle: 'medium' }) : ''}
                </div>
              </div>
              <OrderStatusBadge status={order.status} />
              <PaymentStatusBadge status={order.payment_status} />
              <div className="order-amount">{COP(order.total)}</div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
