import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { CheckCircle, ShoppingCart, XCircle, AlertTriangle, PackageX, CreditCard } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../context/ToastContext';

// El POST /api/checkout ahora SOLO devuelve 200/201 si la SAGA termino en PAID.
// Cualquier otro caso devuelve un error HTTP con detalle estructurado y NO
// crea Order (vive en failed_checkout_attempts para auditoria). El frontend
// debe presentar al cliente un mensaje claro segun el codigo.

const ERROR_CONFIG = {
  out_of_stock:        { icon: <PackageX size={36} />,      title: 'Sin stock',                 sub: 'Algunos productos del carrito ya no tienen stock. Revísalo y vuelve a intentar.', variant: 'error' },
  payment_rejected:    { icon: <CreditCard size={36} />,    title: 'Pago rechazado',            sub: 'La pasarela rechazó el pago. Tu carrito está intacto; intenta con otro método.', variant: 'error' },
  payment_unavailable: { icon: <AlertTriangle size={36} />, title: 'Pasarela no disponible',    sub: 'La pasarela está temporalmente fuera de servicio. Intenta en unos minutos.', variant: 'pending' },
  payment_not_approved:{ icon: <CreditCard size={36} />,    title: 'Pago no aprobado',          sub: 'La pasarela devolvió un estado inesperado. Intenta de nuevo.', variant: 'error' },
  inventory_unavailable:{ icon: <AlertTriangle size={36} />, title: 'Inventario no disponible', sub: 'El servicio de inventario no respondió. Intenta en unos minutos.', variant: 'pending' },
  inventory_error:     { icon: <PackageX size={36} />,      title: 'Error de inventario',       sub: 'No fue posible reservar el stock. Intenta de nuevo.', variant: 'error' },
  cart_empty:          { icon: <ShoppingCart size={36} />,  title: 'Carrito vacío',             sub: 'Agrega productos al carrito antes de pagar.', variant: 'error' },
};

export default function PaymentResult() {
  const { state } = useLocation();
  const toast = useToast();
  const [order, setOrder] = useState(null);
  const [failure, setFailure] = useState(null); // { code, message, unavailable? }
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
    setFailure(null);
    try {
      const { data } = await api.post('/checkout', {
        ...state.checkout,
        additional_costs: 0,
        discount: 0,
      }, {
        headers: { 'Idempotency-Key': `${Date.now()}-${Math.random().toString(36).slice(2, 10)}` },
      });
      setOrder(data);
      toast('¡Pago aprobado!', 'success');
    } catch (err) {
      const d = err.response?.data || {};
      const code = d.code || 'payment_not_approved';
      const message = d.message || d.detail || 'No se pudo finalizar el pedido.';
      setFailure({ code, message, unavailable: d.unavailable });
      toast(message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // PAGO EXITOSO
  if (order) {
    return (
      <div className="payment-result-page">
        <div className="payment-result-card">
          <div className="payment-icon-wrap success"><CheckCircle size={36} /></div>
          <h2>¡Pago aprobado!</h2>
          <p>Tu pedido fue creado y está en proceso.</p>
          <div style={{
            background: 'var(--neutral-50)', border: '1px solid var(--neutral-200)',
            borderRadius: 'var(--radius-md)', padding: '1rem',
            marginBottom: '1.5rem', textAlign: 'left',
          }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--neutral-500)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.35rem' }}>
              Código de pedido
            </div>
            <div className="font-mono" style={{ fontWeight: 800, fontSize: '1.1rem' }}>
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

  // PAGO FALLIDO (con código del backend)
  if (failure) {
    const cfg = ERROR_CONFIG[failure.code] || ERROR_CONFIG.payment_not_approved;
    return (
      <div className="payment-result-page">
        <div className="payment-result-card">
          <div className={`payment-icon-wrap ${cfg.variant}`}>{cfg.icon}</div>
          <h2>{cfg.title}</h2>
          <p>{failure.message || cfg.sub}</p>

          {/* Si hay items sin stock, mostrar cuáles */}
          {failure.unavailable && Array.isArray(failure.unavailable) && failure.unavailable.length > 0 && (
            <div style={{
              background: 'var(--error-bg)', border: '1px solid var(--error-border)',
              borderRadius: 'var(--radius-md)', padding: '0.75rem 1rem',
              marginBottom: '1rem', textAlign: 'left', fontSize: '0.8125rem',
            }}>
              <div style={{ fontWeight: 700, marginBottom: 4, color: 'var(--error-text)' }}>
                Items sin disponibilidad:
              </div>
              <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                {failure.unavailable.map((u, i) => (
                  <li key={i}>
                    Variante #{u.variant_id} — {u.reason === 'sin_stock'
                      ? `solo ${u.available} disponibles, pediste ${u.requested}`
                      : u.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ display: 'grid', gap: '0.6rem' }}>
            <button className="btn btn-primary btn-full" onClick={() => { setFailure(null); pay(); }} disabled={loading}>
              {loading ? 'Intentando…' : 'Intentar de nuevo'}
            </button>
            <Link to="/carrito" className="btn btn-secondary btn-full">
              Volver al carrito
            </Link>
            <Link to="/catalogo" style={{ textAlign: 'center', color: 'var(--neutral-500)', fontSize: '0.875rem', textDecoration: 'none', marginTop: 4 }}>
              ← Ir al catálogo
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // PANTALLA INICIAL — confirmar pago
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
