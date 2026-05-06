import { Link } from 'react-router-dom';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';

export default function Cart() {
  const { data: cart, loading, error, setData } = useAsync(async () => {
    const { data } = await api.get('/cart');
    return data;
  }, []);

  const updateQuantity = async (item, quantity) => {
    const { data } = await api.put(`/cart/items/${item.id}`, { quantity });
    setData(data);
  };

  const removeItem = async (item) => {
    await api.delete(`/cart/items/${item.id}`);
    const { data } = await api.get('/cart');
    setData(data);
  };

  if (loading) return <div className="state">Cargando carrito...</div>;
  if (error) return <div className="state error">{error}</div>;

  return (
    <main className="page-shell">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Compra en curso</span>
          <h1>Carrito</h1>
        </div>
        <Link className="button-link" to="/checkout">Continuar checkout</Link>
      </div>
      <div className="cart-layout">
        <section className="cart-list">
          {cart.items.map((item) => (
            <article className="cart-item" key={item.id}>
              <img src={item.image_url} alt={item.product_name} />
              <div>
                <strong>{item.product_name}</strong>
                <p>{item.variant_description} | SKU {item.sku}</p>
                <span>Stock disponible: {item.available_stock}</span>
              </div>
              <input
                type="number"
                min="1"
                max={item.available_stock}
                value={item.quantity}
                onChange={(event) => updateQuantity(item, Number(event.target.value))}
                aria-label={`Cantidad de ${item.product_name}`}
              />
              <strong>${Number(item.total).toLocaleString('es-CO')}</strong>
              <button className="ghost-button" onClick={() => removeItem(item)}>Eliminar</button>
            </article>
          ))}
          {cart.items.length === 0 && <p className="state">Tu carrito esta vacio.</p>}
        </section>
        <aside className="summary-panel">
          <span>Subtotal</span>
          <strong>${Number(cart.subtotal).toLocaleString('es-CO')}</strong>
          <Link className="button-link product-action" to="/checkout">Ir a checkout</Link>
        </aside>
      </div>
    </main>
  );
}

