import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CreditCard, MapPin, User } from 'lucide-react';
import api from '../api/client';
import { useToast } from '../context/ToastContext';

const initialForm = {
  delivery_name:    '',
  delivery_address: '',
  delivery_city:    '',
  billing_document: '',
  contact_phone:    '',
  contact_email:    '',
  discount:         0,
  additional_costs: 0,
};

// En la arquitectura de microservicios, POST /api/checkout ejecuta TODA la
// SAGA (reservar -> pagar -> confirmar/liberar). Por eso este formulario
// calcula el resumen localmente desde el carrito y deja el pago a la
// siguiente pantalla (PaymentResult).
export default function Checkout() {
  const navigate = useNavigate();
  const toast = useToast();
  const [form, setForm] = useState(initialForm);
  const [cart, setCart] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/cart').then(({ data }) => {
      setCart(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const upd = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const calculate = (e) => {
    e.preventDefault();
    if (!cart || !cart.items || cart.items.length === 0) {
      toast('Tu carrito esta vacio. Agrega productos antes del checkout.', 'error');
      return;
    }
    const subtotal = Number(cart.subtotal || 0);
    const additional = Number(form.additional_costs || 0);
    const discount = Number(form.discount || 0);
    const total = Math.max(0, subtotal + additional - discount);
    setSummary({ subtotal, additional_costs: additional, discount, total });
    toast('Resumen calculado. Procede al pago.', 'success');
  };

  if (loading) return <div className="state">Cargando carrito...</div>;
  if (!cart || cart.items.length === 0) {
    return (
      <main className="page-shell">
        <div className="state">Tu carrito esta vacio. Vuelve al catalogo.</div>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <div className="section-heading" style={{ marginBottom: '1.5rem' }}>
        <div>
          <span className="eyebrow">Compra</span>
          <h1>Checkout</h1>
        </div>
      </div>

      <form onSubmit={calculate}>
        <div className="checkout-layout">
          {/* Left — form */}
          <div>
            {/* Delivery */}
            <div className="checkout-form-section">
              <h3><MapPin size={16} /> Datos de entrega</h3>
              <div className="fields">
                <label>Nombre completo *
                  <input value={form.delivery_name} onChange={upd('delivery_name')} required />
                </label>
                <div className="fields-row">
                  <label>Ciudad *
                    <input value={form.delivery_city} onChange={upd('delivery_city')} required />
                  </label>
                  <label>Teléfono *
                    <input type="tel" value={form.contact_phone} onChange={upd('contact_phone')} required />
                  </label>
                </div>
                <label>Dirección de entrega *
                  <input value={form.delivery_address} onChange={upd('delivery_address')} required />
                </label>
              </div>
            </div>

            {/* Billing */}
            <div className="checkout-form-section">
              <h3><User size={16} /> Datos de facturación</h3>
              <div className="fields">
                <div className="fields-row">
                  <label>Email de contacto *
                    <input type="email" value={form.contact_email} onChange={upd('contact_email')} required />
                  </label>
                  <label>Documento (NIT/CC) *
                    <input value={form.billing_document} onChange={upd('billing_document')} required />
                  </label>
                </div>
              </div>
            </div>

            {/* Extras */}
            <div className="checkout-form-section">
              <h3><CreditCard size={16} /> Ajustes de precio</h3>
              <div className="fields">
                <div className="fields-row">
                  <label>Costos adicionales (COP)
                    <input type="number" min="0" value={form.additional_costs} onChange={upd('additional_costs')} />
                  </label>
                  <label>Descuento (COP)
                    <input type="number" min="0" value={form.discount} onChange={upd('discount')} />
                  </label>
                </div>
              </div>
            </div>

            <button type="submit" className="btn btn-primary btn-full btn-lg">
              Calcular total
            </button>
          </div>

          {/* Right — summary */}
          <aside className="cart-summary" style={{ top: 'calc(var(--topbar-h) + 1rem)' }}>
            <h2>Resumen</h2>
            <div className="summary-row">
              <span>Items en carrito</span>
              <span>{cart.item_count}</span>
            </div>
            {summary ? (
              <>
                <div className="summary-row">
                  <span>Subtotal</span>
                  <span>${Number(summary.subtotal).toLocaleString('es-CO')}</span>
                </div>
                <div className="summary-row">
                  <span>Costos adicionales</span>
                  <span>${Number(summary.additional_costs).toLocaleString('es-CO')}</span>
                </div>
                <div className="summary-row">
                  <span>Descuento</span>
                  <span style={{ color: 'var(--brand-600)' }}>-${Number(summary.discount).toLocaleString('es-CO')}</span>
                </div>
                <div className="summary-row total">
                  <span>Total a pagar</span>
                  <span>${Number(summary.total).toLocaleString('es-CO')}</span>
                </div>
                <button
                  type="button"
                  className="btn btn-primary btn-full btn-lg"
                  style={{ marginTop: '1.25rem' }}
                  onClick={() => navigate('/pago', { state: { checkout: form, summary } })}
                >
                  Ir a pagar →
                </button>
              </>
            ) : (
              <div style={{ color: 'var(--neutral-400)', fontSize: '0.875rem', textAlign: 'center', padding: '1.5rem 0' }}>
                Completa los datos y calcula el total para continuar.
              </div>
            )}
          </aside>
        </div>
      </form>
    </main>
  );
}
