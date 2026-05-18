import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ShoppingCart, Star } from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../context/ToastContext';

function StarRating({ rating, count }) {
  return (
    <div className="rating-row">
      {[1,2,3,4,5].map((i) => (
        <Star
          key={i}
          size={16}
          fill={i <= Math.round(rating) ? 'currentColor' : 'none'}
          color={i <= Math.round(rating) ? '#ca8a04' : '#c5ccbf'}
        />
      ))}
      <strong style={{ color: 'var(--neutral-900)', marginLeft: 4 }}>{Number(rating || 0).toFixed(1)}</strong>
      <span>({count} reseña{count !== 1 ? 's' : ''})</span>
    </div>
  );
}

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const toast = useToast();
  const [variantId, setVariantId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [activeImg, setActiveImg] = useState(0);
  const [adding, setAdding] = useState(false);

  const { data, loading, error } = useAsync(async () => {
    const [product, reviews] = await Promise.all([
      api.get(`/products/${id}`),
      // En microservicios las resenas de un producto las sirve Commerce, no Catalog
      api.get(`/reviews/product/${id}`),
    ]);
    return { product: product.data, reviews: reviews.data };
  }, [id]);

  const selectedVariant = useMemo(
    () => data?.product?.variants.find((v) => String(v.id) === String(variantId)),
    [data, variantId],
  );

  if (loading) {
    return (
      <main className="page-shell">
        <div className="product-detail">
          <div className="skeleton skeleton-image" />
          <div style={{ display: 'grid', gap: '1rem' }}>
            {[...Array(5)].map((_, i) => (
              <div key={i} className="skeleton skeleton-text" style={{ width: `${80 - i * 10}%`, height: i === 0 ? 36 : 16 }} />
            ))}
          </div>
        </div>
      </main>
    );
  }

  if (error) return <div className="state error">Producto no encontrado.</div>;

  const product = data.product;
  const images = product.gallery?.length
    ? product.gallery
    : [{ id: 'main', image_url: product.image_url || 'https://images.unsplash.com/photo-1523381294911-8d3cead13475?w=800&q=80', alt_text: product.name }];

  const addToCart = async () => {
    if (!isAuthenticated) { navigate('/login'); return; }
    if (!selectedVariant) { toast('Selecciona una variante primero.', 'warning'); return; }
    if (selectedVariant.stock < 1) { toast('Esta variante no tiene stock disponible.', 'error'); return; }
    if (quantity > selectedVariant.stock) { toast('Cantidad mayor al stock disponible.', 'error'); return; }
    setAdding(true);
    try {
      await api.post('/cart/items', { variant_id: selectedVariant.id, quantity });
      toast('Producto agregado al carrito.', 'success', '¡Listo!');
    } catch (err) {
      toast(err.response?.data?.detail || 'No se pudo agregar al carrito.', 'error');
    } finally { setAdding(false); }
  };

  return (
    <main className="page-shell">
      <div className="product-detail">
        {/* Gallery */}
        <section className="product-gallery">
          <img
            className="detail-image"
            src={images[activeImg]?.image_url || images[0]?.image_url}
            alt={images[activeImg]?.alt_text || product.name}
          />
          {images.length > 1 && (
            <div className="thumb-row">
              {images.map((img, i) => (
                <img
                  key={img.id}
                  src={img.image_url}
                  alt={img.alt_text || product.name}
                  className={i === activeImg ? 'active' : ''}
                  onClick={() => setActiveImg(i)}
                />
              ))}
            </div>
          )}
        </section>

        {/* Info */}
        <section className="detail-panel">
          <span className="category-chip">{product.category_name}</span>
          <h1>{product.name}</h1>
          <StarRating rating={product.average_rating} count={product.reviews_count} />
          <p>{product.long_description || product.description}</p>
          {!variantId && (
            <strong className="detail-price">${Number(product.base_price).toLocaleString('es-CO')}</strong>
          )}

          {/* Variant picker — estilo Nike */}
          {product.variants.length > 0 && (() => {
            const hasSizes  = product.variants.some((v) => v.size);
            const hasColors = product.variants.some((v) => v.color);
            const selectedV = product.variants.find((v) => String(v.id) === String(variantId));

            return (
              <div style={{ marginBottom: '0.75rem' }}>
                {selectedV && (
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '0.75rem' }}>
                    <strong style={{ fontSize: '1.5rem', color: 'var(--neutral-900)' }}>
                      ${Number(selectedV.price).toLocaleString('es-CO')}
                    </strong>
                    {selectedV.price !== product.base_price && (
                      <span style={{ fontSize: '0.875rem', color: 'var(--neutral-400)', textDecoration: 'line-through' }}>
                        ${Number(product.base_price).toLocaleString('es-CO')}
                      </span>
                    )}
                  </div>
                )}

                {hasColors && (
                  <div style={{ marginBottom: '0.75rem' }}>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-700)', marginBottom: '0.4rem' }}>
                      Color{selectedV?.color ? `: ${selectedV.color}` : ''}
                    </div>
                    <div className="color-grid">
                      {product.variants.filter((v) => !hasSizes || !variantId || v.color).map((v) => (
                        <button
                          key={v.id}
                          title={v.color}
                          disabled={v.stock <= 0}
                          className={`color-swatch${String(v.id) === String(variantId) ? ' selected' : ''}`}
                          style={{
                            background: v.color?.startsWith('#') ? v.color : v.color || '#ccc',
                            opacity: v.stock <= 0 ? 0.35 : 1,
                          }}
                          onClick={() => { setVariantId(String(v.id)); setQuantity(1); }}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {hasSizes && (
                  <div style={{ marginBottom: '0.75rem' }}>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-700)', marginBottom: '0.4rem' }}>
                      Talla{selectedV?.size ? `: ${selectedV.size}` : ' — selecciona una'}
                    </div>
                    <div className="size-grid">
                      {product.variants.map((v) => (
                        <button
                          key={v.id}
                          disabled={v.stock <= 0}
                          className={`size-btn${String(v.id) === String(variantId) ? ' selected' : ''}`}
                          onClick={() => { setVariantId(String(v.id)); setQuantity(1); }}
                        >
                          {v.size || v.custom_attribute || v.sku}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {!hasSizes && !hasColors && (
                  <label>
                    Variante
                    <select value={variantId} onChange={(e) => { setVariantId(e.target.value); setQuantity(1); }}>
                      <option value="">Selecciona variante</option>
                      {product.variants.map((v) => (
                        <option key={v.id} value={v.id} disabled={v.stock <= 0}>
                          {v.sku}{v.stock <= 0 ? ' (agotado)' : ` (${v.stock} uds)`}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
            );
          })()}

          {selectedVariant && (
            <>
              <label>
                Cantidad
                <input
                  type="number"
                  min="1"
                  max={selectedVariant.stock}
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, Math.min(Number(e.target.value), selectedVariant.stock)))}
                />
              </label>
              <div
                className={`alert ${selectedVariant.stock > 0 ? 'success' : 'error'}`}
                style={{ marginBottom: '0.75rem' }}
              >
                {selectedVariant.stock > 0
                  ? `✓ ${selectedVariant.stock} unidades disponibles para esta variante`
                  : '✗ Variante sin stock — selecciona otra'}
              </div>
            </>
          )}

          <button
            className="btn btn-primary btn-full btn-lg"
            onClick={addToCart}
            disabled={adding || (selectedVariant && selectedVariant.stock <= 0)}
            style={{ gap: '0.6rem' }}
          >
            <ShoppingCart size={18} />
            {adding ? 'Agregando…' : 'Agregar al carrito'}
          </button>

          {!isAuthenticated && (
            <p className="alert info" style={{ marginTop: '0.75rem' }}>
              <a href="/login" style={{ color: 'var(--info-text)', fontWeight: 700 }}>Inicia sesión</a> para agregar al carrito.
            </p>
          )}

          {/* Extra info */}
          <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'var(--neutral-50)', borderRadius: 'var(--radius-md)', border: '1px solid var(--neutral-200)' }}>
            <div style={{ fontWeight: 700, marginBottom: '0.5rem', fontSize: '0.875rem' }}>Información del producto</div>
            <div style={{ display: 'grid', gap: '0.3rem', fontSize: '0.8125rem', color: 'var(--neutral-600)' }}>
              <div>✓ Precio base: ${Number(product.base_price).toLocaleString('es-CO')}</div>
              <div>✓ {product.variants.length} variante(s) disponible(s)</div>
              <div>✓ Stock en tiempo real verificado</div>
            </div>
          </div>
        </section>

        {/* Reviews */}
        <section className="reviews-panel">
          <div className="section-heading">
            <h2>Reseñas</h2>
            {product.reviews_count > 0 && <span style={{ color: 'var(--neutral-500)', fontSize: '0.875rem' }}>{product.reviews_count} reseña(s)</span>}
          </div>
          {data.reviews.length === 0 ? (
            <div className="state">Sé el primero en dejar una reseña sobre este producto.</div>
          ) : (
            data.reviews.map((review) => (
              <article key={review.id} className="review-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong>{review.user_name}</strong>
                  <span style={{ fontSize: '0.75rem', color: 'var(--neutral-400)' }}>Compra verificada</span>
                </div>
                <div className="stars">{'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)}</div>
                <p>{review.comment}</p>
              </article>
            ))
          )}
        </section>
      </div>
    </main>
  );
}
