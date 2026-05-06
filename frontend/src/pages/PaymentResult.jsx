import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { CheckCircle, Clock, ShoppingCart, XCircle } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../context/ToastContext';

const RESULT_CONFIG = {
  aprobado:  { icon: <CheckCircle size={36} />, title: '¡Pago aprobado!',   sub: 'Tu pedido fue creado y está en proceso.', variant: 'success' },
  rechazado: { icon: <XCircle    size={36} />, title: 'Pago rechazado',    sub: 'El pago no fue procesado. Intenta con otro método.', variant: 'error' },
  pendiente: { icon: <Clock      size={36} />, title: 'Pago pendiente',    sub: 'El pago está en revisión. Te notificaremos cuando se confirme.', variant: 'pending' },
};

export default function PaymentResult() {
  const { state } = useLocation();
  const toast = useToast();
  const [simStatus, setSimStatus] = useState('aprobado');
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
      const { data: payment } = await api.post('/payments/simulate', {
        amount: state.summary.total,
        requested_status: simStatus,
      });
      const { data: createdOrder } = await api.post('/orders', {
        ...state.checkout,
        payment_status: payment.status,
        transaction_reference: payment.transaction_reference,
        response_message: payment.response_message,
      });
      setOrder(createdOrder);
      const cfg = RESULT_CONFIG[createdOrder.payment_status];
      toast(cfg.title, createdOrder.payment_status === 'aprobado' ? 'success' : createdOrder.payment_status === 'rechazado' ? 'error' : 'warning');
    } catch (err) {
      toast(err.response?.data?.detail || 'No se pudo finalizar el pedido.', 'error');
    } finally {
      setLoading(false);
    }
  };

  if (order) {
    const cfg = RESULT_CONFIG[order.payment_status] || RESULT_CONFIG.pendiente;
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
          </div>
          <div style={{ display: 'grid', gap: '0.6rem' }}>
            <Link to={`/pedidos/${order.id}`} className="btn btn-primary btn-full">
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
        <p>Elige el resultado a simular para este pago de <strong>${Number(state.summary.total).toLocaleString('es-CO')}</strong>.</p>

        {/* Simulated gateway selector */}
        <div style={{
          background: 'var(--neutral-50)',
          border: '1px solid var(--neutral-200)',
          borderRadius: 'var(--radius-lg)',
          padding: '1.25rem',
          marginBottom: '1.5rem',
          textAlign: 'left',
        }}>
          <div style={{ fontSize: '0.78rem', fontWeight: 800, color: 'var(--neutral-500)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.75rem' }}>
            Simular resultado de pago
          </div>
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {[
              { value: 'aprobado',  label: 'Pago aprobado',  desc: 'El pedido se crea y el inventario se descuenta', color: 'var(--success-text)' },
              { value: 'rechazado', label: 'Pago rechazado', desc: 'El pedido se crea pero no descuenta inventario',  color: 'var(--error-text)' },
              { value: 'pendiente', label: 'Pago pendiente', desc: 'El pedido queda en espera de confirmación',       color: 'var(--warning-text)' },
            ].map((opt) => (
              <label
                key={opt.value}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.75rem',
                  padding: '0.75rem',
                  borderRadius: 'var(--radius-sm)',
                  border: `1.5px solid ${simStatus === opt.value ? opt.color : 'var(--neutral-200)'}`,
                  cursor: 'pointer',
                  background: simStatus === opt.value ? `${opt.color}10` : '#fff',
                  transition: 'all 150ms',
                  margin: 0,
                }}
              >
                <input
                  type="radio"
                  name="payment_status"
                  value={opt.value}
                  checked={simStatus === opt.value}
                  onChange={(e) => setSimStatus(e.target.value)}
                  style={{ width: 'auto', accentColor: opt.color }}
                />
                <div>
                  <strong style={{ display: 'block', color: opt.color, fontSize: '0.875rem' }}>{opt.label}</strong>
                  <span style={{ fontSize: '0.78rem', color: 'var(--neutral-500)' }}>{opt.desc}</span>
                </div>
              </label>
            ))}
          </div>
        </div>

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
