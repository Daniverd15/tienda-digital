import { Link } from 'react-router-dom';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';

export default function MyOrders() {
  const { data: orders, loading, error } = useAsync(async () => {
    const { data } = await api.get('/orders/my');
    return data;
  }, []);

  if (loading) return <div className="state">Cargando pedidos...</div>;
  if (error) return <div className="state error">{error}</div>;

  return (
    <main className="page-shell">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Historial</span>
          <h1>Mis pedidos</h1>
        </div>
        <Link className="ghost-link" to="/notificaciones">Notificaciones</Link>
      </div>
      <div className="table-list">
        {orders.map((order) => (
          <Link className="row-card" to={`/pedidos/${order.id}`} key={order.id}>
            <strong>{order.order_code}</strong>
            <span>{order.status}</span>
            <span>Pago {order.payment_status}</span>
            <span>${Number(order.total).toLocaleString('es-CO')}</span>
          </Link>
        ))}
        {orders.length === 0 && <p className="state">Aun no tienes pedidos.</p>}
      </div>
    </main>
  );
}

