import api from '../api/client';
import { useAsync } from '../hooks/useAsync';

const statuses = ['pendiente_pago', 'preparacion', 'enviado', 'entregado', 'cancelado', 'rechazado'];

export default function AdminOrders() {
  const { data: orders, loading, error, setData } = useAsync(async () => {
    const { data } = await api.get('/admin/orders');
    return data;
  }, []);

  const updateStatus = async (order, status) => {
    const { data } = await api.put(`/admin/orders/${order.id}/status`, { status });
    setData(orders.map((item) => (item.id === order.id ? data : item)));
  };

  if (loading) return <div className="state">Cargando pedidos administrativos...</div>;
  if (error) return <div className="state error">{error}</div>;

  return (
    <main className="page-shell">
      <span className="eyebrow">Operacion</span>
      <h1>Gestion de pedidos</h1>
      <div className="table-list">
        {orders.map((order) => (
          <article className="row-card admin-row" key={order.id}>
            <strong>{order.order_code}</strong>
            <span>Pago {order.payment_status}</span>
            <span>${Number(order.total).toLocaleString('es-CO')}</span>
            <select value={order.status} onChange={(event) => updateStatus(order, event.target.value)}>
              {statuses.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </article>
        ))}
      </div>
    </main>
  );
}

