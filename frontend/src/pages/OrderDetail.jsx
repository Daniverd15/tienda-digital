import { useParams } from 'react-router-dom';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';

export default function OrderDetail() {
  const { id } = useParams();
  const { data: order, loading, error } = useAsync(async () => {
    const { data } = await api.get(`/orders/${id}`);
    return data;
  }, [id]);

  if (loading) return <div className="state">Cargando pedido...</div>;
  if (error) return <div className="state error">{error}</div>;

  return (
    <main className="page-shell">
      <span className="eyebrow">Pedido</span>
      <h1>{order.order_code}</h1>
      <div className="order-summary">
        <span>Estado: <strong>{order.status}</strong></span>
        <span>Pago: <strong>{order.payment_status}</strong></span>
        <span>Total: <strong>${Number(order.total).toLocaleString('es-CO')}</strong></span>
        <span>Entrega: {order.delivery_address}, {order.delivery_city}</span>
      </div>
      <section className="table-list">
        {order.items.map((item) => (
          <article className="row-card" key={item.id}>
            <strong>{item.product_name}</strong>
            <span>{item.variant_description}</span>
            <span>Cantidad {item.quantity}</span>
            <span>${Number(item.total).toLocaleString('es-CO')}</span>
          </article>
        ))}
      </section>
    </main>
  );
}

