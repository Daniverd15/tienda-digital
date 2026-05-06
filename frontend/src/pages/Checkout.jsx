import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';

const initialForm = {
  delivery_name: '',
  delivery_address: '',
  delivery_city: '',
  billing_document: '',
  contact_phone: '',
  contact_email: '',
  discount: 0,
  additional_costs: 0
};

export default function Checkout() {
  const navigate = useNavigate();
  const [form, setForm] = useState(initialForm);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');

  const calculate = async (event) => {
    event.preventDefault();
    setError('');
    try {
      const { data } = await api.post('/checkout', form);
      setSummary(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'No fue posible validar el checkout.');
    }
  };

  return (
    <main className="page-shell checkout-grid">
      <form className="checkout-form" onSubmit={calculate}>
        <span className="eyebrow">Datos de compra</span>
        <h1>Checkout</h1>
        {error && <p className="alert error">{error}</p>}
        {Object.keys(initialForm).map((field) => (
          <label key={field}>
            {field.replaceAll('_', ' ')}
            <input
              type={field.includes('costs') || field === 'discount' ? 'number' : field.includes('email') ? 'email' : 'text'}
              value={form[field]}
              onChange={(event) => setForm({ ...form, [field]: event.target.value })}
              required={!['discount', 'additional_costs'].includes(field)}
            />
          </label>
        ))}
        <button className="primary-button">Validar stock y calcular</button>
      </form>
      <aside className="summary-panel">
        <h2>Resumen</h2>
        {summary ? (
          <>
            <span>Subtotal: ${Number(summary.subtotal).toLocaleString('es-CO')}</span>
            <span>Adicionales: ${Number(summary.additional_costs).toLocaleString('es-CO')}</span>
            <span>Descuento: ${Number(summary.discount).toLocaleString('es-CO')}</span>
            <strong>Total: ${Number(summary.total).toLocaleString('es-CO')}</strong>
            <button className="primary-button" onClick={() => navigate('/pago', { state: { checkout: form, summary } })}>
              Pagar
            </button>
          </>
        ) : (
          <p>Completa los datos para calcular el total.</p>
        )}
      </aside>
    </main>
  );
}

