import { Link } from 'react-router-dom';
import { Minus, Plus, ShoppingBag, Trash2 } from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../context/ToastContext';

export default function Cart() {
  const toast = useToast();
  const { data: cart, loading, error, setData } = useAsync(async () => {
    const { data } = await api.get('/cart');
    return data;
  }, []);

  const updateQuantity = async (item, qty) => {
    if (qty < 1 || qty > item.available_stock) return;
    try {
      const { data } = await api.put(`/cart/items/${item.id}`, { quantity: qty });
      setData(data);
    } catch (err) {
      toast(err.response?.data?.detail || 'No se pudo actualizar la cantidad.', 'error');
    }
  };

  const removeItem = async (item) => {
    try {
      await api.delete(`/cart/items/${item.id}`);
      const { data } = await api.get('/cart');
      setData(data);
      toast('Producto eliminado del carrito.', 'success');
    } catch {
      toast('Error al eliminar el artículo.', 'error');
    }
  };

  if (loading) return <div className="state">Cargando carrito...</div>;
  if (error)   return <div className="state error">{error}</div>;

  const itemCount = cart.items.reduce((s, i) => s + i.quantity, 0);

  return (
    <main className="page-shell">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Compra en curso</span>
          <h1>Mi carrito {itemCount > 0 && <span style={{ color: 'var(--neutral-500)', fontWeight: 400, fontSize: '1.25rem' }}>({itemCount} artículo{itemCount !== 1 ? 's' : ''})</span>}</h1>
        </div>
      </div>

      {cart.items.length === 0 ? (
        <div className="cart-empty">
          <ShoppingBag size={56} style={{ color: 'var(--neutral-300)', margin: '0 auto 1rem' }} />
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--neutral-600)', marginBottom: '0.5rem' }}>
            Tu carrito está vacío
          </div>
          <p style={{ color: 'var(--neutral-400)', marginBottom: '1.5rem' }}>Explora el catálogo y agrega productos.</p>
          <Link className="btn btn-primary" to="/catalogo">Ir al catálogo</Link>
        </div>
      ) : (
        <div className="cart-layout">
          {/* Items */}
          <section>
            {cart.items.map((item) => (
              <div key={item.id} className="cart-item">
                <img
                  src={item.image_url || 'https://images.unsplash.com/photo-1523381294911-8d3cead13475?w=200&q=80'}
                  alt={item.product_name}
                />
                <div className="cart-item-info">
                  <strong>{item.product_name}</strong>
                  <p>{item.variant_description} · SKU {item.sku}</p>
                  <span>Stock disponible: {item.available_stock}</span>
                </div>
                {/* Qty controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <button
                    className="btn btn-secondary btn-sm btn-icon"
                    onClick={() => updateQuantity(item, item.quantity - 1)}
                    disabled={item.quantity <= 1}
                  >
                    <Minus size={13} />
                  </button>
                  <span style={{ fontWeight: 700, minWidth: 24, textAlign: 'center' }}>{item.quantity}</span>
                  <button
                    className="btn btn-secondary btn-sm btn-icon"
                    onClick={() => updateQuantity(item, item.quantity + 1)}
                    disabled={item.quantity >= item.available_stock}
                  >
                    <Plus size={13} />
                  </button>
                </div>
                <strong style={{ fontWeight: 800, fontSize: '1rem', whiteSpace: 'nowrap' }}>
                  ${Number(item.total).toLocaleString('es-CO')}
                </strong>
                <button
                  className="btn btn-danger btn-sm btn-icon"
                  onClick={() => removeItem(item)}
                  title="Eliminar"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </section>

          {/* Summary */}
          <aside className="cart-summary">
            <h2>Resumen del pedido</h2>
            <div className="summary-row">
              <span>Subtotal ({itemCount} artículos)</span>
              <span>${Number(cart.subtotal).toLocaleString('es-CO')}</span>
            </div>
            <div className="summary-row">
              <span>Envío</span>
              <span style={{ color: 'var(--brand-600)', fontWeight: 600 }}>Se calcula al pagar</span>
            </div>
            <div className="summary-row total">
              <span>Subtotal</span>
              <span>${Number(cart.subtotal).toLocaleString('es-CO')}</span>
            </div>
            <Link
              to="/checkout"
              className="btn btn-primary btn-full btn-lg"
              style={{ marginTop: '1rem' }}
            >
              Continuar al pago
            </Link>
            <Link to="/catalogo" className="ghost-link" style={{ display: 'flex', justifyContent: 'center', marginTop: '0.75rem', fontSize: '0.875rem' }}>
              ← Seguir comprando
            </Link>
          </aside>
        </div>
      )}
    </main>
  );
}
