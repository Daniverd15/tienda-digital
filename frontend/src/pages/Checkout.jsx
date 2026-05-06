import { useState } from 'react';
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

export default function Checkout() {
  const navigate = useNavigate();
  const toast = useToast();
  const [form, setForm] = useState(initialForm);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  const upd = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const calculate = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await api.post('/checkout', {
        ...form,
        discount: Number(form.discount),
        additional_costs: Number(form.additional_costs),
      });
      setSummary(data);
      toast('Stock verificado. Revisa el resumen y procede al pago.', 'success');
    } catch (err) {
      toast(err.response?.data?.detail || 'No se pudo validar el checkout.', 'error');
    } finally { setLoading(false); }
  };

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

            <button type="submit" className="btn btn-primary btn-full btn-lg" disabled={loading}>
              {loading ? 'Validando stock…' : 'Verificar stock y calcular total'}
            </button>
          </div>

          {/* Right — summary */}
          <aside className="cart-summary" style={{ top: 'calc(var(--topbar-h) + 1rem)' }}>
            <h2>Resumen</h2>
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
                <div className="alert success" style={{ marginTop: '0.75rem', fontSize: '0.8125rem' }}>
                  Stock verificado. Puedes proceder al pago.
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--neutral-400)', fontSize: '0.875rem', textAlign: 'center', padding: '1.5rem 0' }}>
                Completa los datos y verifica el stock para ver el total.
              </div>
            )}
          </aside>
        </div>
      </form>
    </main>
  );
}
