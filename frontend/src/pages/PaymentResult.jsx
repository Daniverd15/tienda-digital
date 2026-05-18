import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { CheckCircle, Clock, ShoppingCart, XCircle } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../context/ToastContext';

// En arquitectura de microservicios, POST /api/checkout ejecuta la SAGA
// completa (reserva + cobro + confirm/release).
const RESULT_CONFIG = {
  APPROVED:  { icon: <CheckCircle size={36} />, title: '¡Pago aprobado!',   sub: 'Tu pedido fue creado y está en proceso.', variant: 'success' },
  REJECTED:  { icon: <XCircle    size={36} />, title: 'Pago rechazado',    sub: 'El pago no fue procesado. Intenta con otro método.', variant: 'error' },
  PENDING:   { icon: <Clock      size={36} />, title: 'Pago pendiente',    sub: 'El pago está en revisión. Te notificaremos cuando se confirme.', variant: 'pending' },
  FAILED:    { icon: <XCircle    size={36} />, title: 'Pasarela no disponible', sub: 'No pudimos comunicarnos con la pasarela. El pedido queda pendiente.', variant: 'error' },
};

export default function PaymentResult() {
  const { state } = useLocation();
  const toast = useToast();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!state?.checkout || !state?.summary) {
    return (
      <div className="payment-result-page">
        <div className="payment-result-card">
          <div className="payment-icon-wrap error"><XCircle size={36} /></div>
          <h2>Sin checkout activo</h2>
          <p>No hay una sesión de pago activa. Ve al carrito para iniciar.</p>
          <Link to="/carrito" className="btn btn-primary btn-full">Ir al carrito</Link>
        </div>
      </div>
    );
  }

  const pay = async () => {
    setLoading(true);
    try {
      const { data } = await api.post('/checkout', {
        ...state.checkout,
        additional_costs: 0,
        discount: 0,
      }, {
        headers: { 'Idempotency-Key': `${Date.now()}-${Math.random().toString(36).slice(2, 10)}` },
      });
      setOrder(data);
      const cfg = RESULT_CONFIG[data.payment_status] || RESULT_CONFIG.PENDING;
      toast(cfg.title, data.payment_status === 'APPROVED' ? 'success' :
                       data.payment_status === 'REJECTED' ? 'error' : 'warning');
    } catch (err) {
      toast(err.response?.data?.detail?.message || err.response?.data?.detail || 'No se pudo finalizar el pedido.', 'error');
    } finally {
      setLoading(false);
    }
  };

  if (order) {
    const cfg = RESULT_CONFIG[order.payment_status] || RESULT_CONFIG.PENDING;
    return (
      <div className="payment-result-page">
        <div className="payment-result-card">
          <div className={`payment-icon-wrap ${cfg.variant}`}>{cfg.icon}</div>
          <h2>{cfg.title}</h2>
          <p>{cfg.sub}</p>
          <div style={{
            background: 'var(--neutral-50)',
            border: '1px solid var(--neutral-200)',
            borderRadius: 'var(--radius-md)',
            padding: '1rem',
            marginBottom: '1.5rem',
            textAlign: 'left',
          }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--neutral-500)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.35rem' }}>
              Código de pedido
            </div>
            <div className="font-mono" style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--neutral-900)' }}>
              {order.order_code}
            </div>
            {order.message && (
              <div style={{ fontSize: '0.8125rem', color: 'var(--neutral-500)', marginTop: '0.5rem' }}>
                {order.message}
              </div>
            )}
          </div>
          <div style={{ display: 'grid', gap: '0.6rem' }}>
            <Link to={`/pedidos/${order.order_id}`} className="btn btn-primary btn-full">
              Ver detalle del pedido
            </Link>
            <Link to="/catalogo" className="btn btn-secondary btn-full">
              Seguir comprando
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="payment-result-page">
      <div className="payment-result-card">
        <div className="payment-icon-wrap pending">
          <ShoppingCart size={36} />
        </div>
        <h2>Pasarela de pago</h2>
        <p>Confirma el pago por <strong>${Number(state.summary.total).toLocaleString('es-CO')}</strong>.</p>

        <button
          className="btn btn-primary btn-full btn-lg"
          onClick={pay}
          disabled={loading}
        >
          {loading ? 'Procesando…' : `Confirmar pago · $${Number(state.summary.total).toLocaleString('es-CO')}`}
        </button>
        <Link to="/checkout" style={{ display: 'block', textAlign: 'center', marginTop: '0.75rem', color: 'var(--neutral-500)', fontSize: '0.875rem', textDecoration: 'none' }}>
          ← Volver al checkout
        </Link>
      </div>
    </div>
  );
}
