import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import api from '../api/client';

export default function PaymentResult() {
  const { state } = useLocation();
  const [status, setStatus] = useState('aprobado');
  const [order, setOrder] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!state?.checkout || !state?.summary) {
    return (
      <main className="page-shell">
        <p className="state error">No hay un checkout activo para pagar.</p>
        <Link className="button-link" to="/carrito">Volver al carrito</Link>
      </main>
    );
  }

  const pay = async () => {
    setLoading(true);
    setError('');
    try {
      const { data: payment } = await api.post('/payments/simulate', {
        amount: state.summary.total,
        requested_status: status
      });
      const { data: createdOrder } = await api.post('/orders', {
        ...state.checkout,
        payment_status: payment.status,
        transaction_reference: payment.transaction_reference,
        response_message: payment.response_message
      });
      setOrder(createdOrder);
    } catch (err) {
      setError(err.response?.data?.detail || 'No fue posible finalizar el pedido.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page-shell payment-page">
      <section className="summary-panel">
        <span className="eyebrow">Pasarela simulada</span>
        <h1>Resultado de pago</h1>
        <label>
          Estado a simular
          <select value={status} onChange={(event) => setStatus(event.target.value)} disabled={Boolean(order)}>
            <option value="aprobado">Aprobado</option>
            <option value="rechazado">Rechazado</option>
            <option value="pendiente">Pendiente</option>
          </select>
        </label>
        <strong>Total: ${Number(state.summary.total).toLocaleString('es-CO')}</strong>
        {error && <p className="alert error">{error}</p>}
        {!order && <button className="primary-button" onClick={pay} disabled={loading}>{loading ? 'Procesando...' : 'Simular pago'}</button>}
        {order && (
          <div className="payment-result">
            <p className={order.payment_status === 'aprobado' ? 'alert success' : 'alert'}>
              Pedido {order.order_code} creado con pago {order.payment_status}.
            </p>
            <Link className="button-link product-action" to={`/pedidos/${order.id}`}>Ver pedido</Link>
          </div>
        )}
      </section>
    </main>
  );
}

