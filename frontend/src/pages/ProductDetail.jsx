import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ShoppingCart, Star, Truck, Shield, RotateCcw } from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useAsync } from '../hooks/useAsync';
import { useToast } from '../context/ToastContext';
import { assetUrl } from '../utils/assets';

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

const variantStock = (variant) => {
  const amount = Number(variant?.available ?? variant?.stock);
  return Number.isFinite(amount) ? amount : 0;
};

/** Clave de color: usa el nombre normalizado para agrupar variantes. */
const colorKey = (v) => (v?.color || '').trim().toLowerCase() || '__nocolor__';

/** Hex visual de un grupo de color. Toma el primer hex disponible, si no, intenta
 *  derivar de un mapa de nombres comunes, si no, gris. */
const KNOWN_COLORS = {
  'negro': '#111111', 'black': '#111111',
  'blanco': '#ffffff', 'white': '#ffffff',
  'rojo': '#dc2626', 'red': '#dc2626',
  'azul': '#2563eb', 'blue': '#2563eb',
  'verde': '#16a34a', 'green': '#16a34a',
  'amarillo': '#facc15', 'yellow': '#facc15',
  'naranja': '#ea580c', 'orange': '#ea580c',
  'rosa': '#ec4899', 'pink': '#ec4899',
  'morado': '#7c3aed', 'purple': '#7c3aed',
  'gris': '#6b7280', 'gray': '#6b7280', 'grey': '#6b7280',
  'marron': '#78350f', 'cafe': '#78350f', 'brown': '#78350f',
  'beige': '#d6c4a8',
};

function colorHex(variant) {
  if (variant?.color_hex) return variant.color_hex;
  const name = (variant?.color || '').trim().toLowerCase();
  return KNOWN_COLORS[name] || '#9ca3af';
}

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const toast = useToast();
  const [selectedColor, setSelectedColor] = useState(null);
  const [variantId, setVariantId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [activeImg, setActiveImg] = useState(0);
  const [adding, setAdding] = useState(false);

  const { data, loading, error } = useAsync(async () => {
    const [product, reviews] = await Promise.all([
      api.get(`/products/${id}`),
      api.get(`/reviews/product/${id}`),
    ]);
    return { product: product.data, reviews: reviews.data };
  }, [id]);

  // Agrupar variantes por color, dentro cada color tiene sus tallas.
  const groupedByColor = useMemo(() => {
    if (!data?.product?.variants) return [];
    const map = new Map();
    data.product.variants.forEach((v) => {
      const k = colorKey(v);
      if (!map.has(k)) map.set(k, { key: k, color: v.color, color_hex: colorHex(v), sizes: [] });
      map.get(k).sizes.push(v);
    });
    return Array.from(map.values());
  }, [data]);

  const hasSizesGlobal = (data?.product?.variants || []).some((v) => v.size);

  // Auto-seleccionar el primer color con stock al cargar
  useEffect(() => {
    if (!data?.product || selectedColor) return;
    const firstWithStock = groupedByColor.find((g) =>
      g.sizes.some((s) => variantStock(s) > 0),
    );
    const targetGroup = firstWithStock || groupedByColor[0];
    if (targetGroup) {
      setSelectedColor(targetGroup.key);
      // Si el producto NO tiene tallas, una variante = un color. Auto-seleccionamos
      // la variant_id directamente para que el botón "Agregar al carrito" funcione.
      if (!hasSizesGlobal) {
        const v = targetGroup.sizes.find((s) => variantStock(s) > 0) || targetGroup.sizes[0];
        if (v) setVariantId(String(v.id));
      }
    }
  }, [data, groupedByColor, selectedColor, hasSizesGlobal]);

  // Al cambiar de color: si NO hay tallas, autoseleccionar la unica variante del color
  const selectColor = (group) => {
    setSelectedColor(group.key);
    setQuantity(1);
    if (!hasSizesGlobal) {
      const v = group.sizes.find((s) => variantStock(s) > 0) || group.sizes[0];
      setVariantId(v ? String(v.id) : '');
    } else {
      setVariantId('');
    }
  };

  const selectedColorGroup = groupedByColor.find((g) => g.key === selectedColor);
  const selectedVariant = useMemo(
    () => data?.product?.variants.find((v) => String(v.id) === String(variantId)),
    [data, variantId],
  );
  const selectedStock = variantStock(selectedVariant);

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

  const hasColors = groupedByColor.some((g) => g.color);
  const hasSizes = product.variants.some((v) => v.size);
  const hasVariants = product.variants.length > 0;

  const addToCart = async () => {
    if (!isAuthenticated) { navigate('/login'); return; }
    if (!selectedVariant) {
      toast(hasSizes ? 'Selecciona una talla primero.' : 'Selecciona una variante primero.', 'warning');
      return;
    }
    if (selectedStock < 1) { toast('Esta variante no tiene stock disponible.', 'error'); return; }
    if (quantity > selectedStock) { toast('Cantidad mayor al stock disponible.', 'error'); return; }
    setAdding(true);
    try {
      await api.post('/cart/items', { variant_id: selectedVariant.id, quantity });
      toast('Producto agregado al carrito.', 'success', '¡Listo!');
    } catch (err) {
      toast(err.response?.data?.detail || 'No se pudo agregar al carrito.', 'error');
    } finally { setAdding(false); }
  };

  const displayPrice = selectedVariant ? Number(selectedVariant.price) : Number(product.base_price);

  return (
    <main className="page-shell">
      <div className="product-detail">
        {/* Gallery */}
        <section className="product-gallery">
          <img
            className="detail-image"
            src={assetUrl(images[activeImg]?.image_url || images[0]?.image_url)}
            alt={images[activeImg]?.alt_text || product.name}
          />
          {images.length > 1 && (
            <div className="thumb-row">
              {images.map((img, i) => (
                <img
                  key={img.id}
                  src={assetUrl(img.image_url)}
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

          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', margin: '0.5rem 0 1rem' }}>
            <strong style={{ fontSize: '1.75rem', color: 'var(--neutral-900)' }}>
              ${Number(displayPrice).toLocaleString('es-CO')}
            </strong>
            {selectedVariant && Number(selectedVariant.price) !== Number(product.base_price) && (
              <span style={{ fontSize: '0.875rem', color: 'var(--neutral-400)', textDecoration: 'line-through' }}>
                ${Number(product.base_price).toLocaleString('es-CO')}
              </span>
            )}
          </div>

          {/* Color picker (Nike-style) */}
          {hasVariants && hasColors && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-700)', marginBottom: '0.5rem' }}>
                Color: <span style={{ fontWeight: 400, color: 'var(--neutral-500)' }}>
                  {selectedColorGroup?.color || 'Selecciona uno'}
                </span>
              </div>
              <div className="color-grid">
                {groupedByColor.map((g) => {
                  const someInStock = g.sizes.some((s) => variantStock(s) > 0);
                  const selected = g.key === selectedColor;
                  return (
                    <button
                      key={g.key}
                      type="button"
                      title={g.color || 'Sin color'}
                      disabled={!someInStock}
                      className={`color-swatch${selected ? ' selected' : ''}${!someInStock ? ' out' : ''}`}
                      style={{ background: g.color_hex }}
                      onClick={() => selectColor(g)}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {/* Size picker dentro del color seleccionado */}
          {hasVariants && hasSizes && selectedColorGroup && (
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-700)' }}>
                  Talla{selectedVariant?.size ? `: ${selectedVariant.size}` : ''}
                </div>
                {!selectedVariant && (
                  <span style={{ fontSize: '0.75rem', color: 'var(--neutral-500)' }}>
                    Selecciona una talla
                  </span>
                )}
              </div>
              <div className="size-grid">
                {selectedColorGroup.sizes.map((v) => {
                  const stock = variantStock(v);
                  const out = stock <= 0;
                  return (
                    <button
                      key={v.id}
                      type="button"
                      disabled={out}
                      className={`size-btn${String(v.id) === String(variantId) ? ' selected' : ''}${out ? ' out' : ''}`}
                      onClick={() => { setVariantId(String(v.id)); setQuantity(1); }}
                      title={out ? 'Agotado' : `${stock} disponibles`}
                    >
                      {v.size || v.custom_attribute || v.sku}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Variante única sin atributos: selector simple */}
          {hasVariants && !hasColors && !hasSizes && (
            <div style={{ marginBottom: '1rem' }}>
              <label>
                Variante
                <select value={variantId} onChange={(e) => { setVariantId(e.target.value); setQuantity(1); }}>
                  <option value="">Selecciona variante</option>
                  {product.variants.map((v) => (
                    <option key={v.id} value={v.id} disabled={variantStock(v) <= 0}>
                      {v.sku}{variantStock(v) <= 0 ? ' (agotado)' : ` (${variantStock(v)} uds)`}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {selectedVariant && (
            <>
              <label>
                Cantidad
                <input
                  type="number"
                  min="1"
                  max={selectedStock}
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, Math.min(Number(e.target.value), selectedStock)))}
                />
              </label>
              <div
                className={`alert ${selectedStock > 0 ? 'success' : 'error'}`}
                style={{ marginBottom: '0.75rem' }}
              >
                {selectedStock > 0
                  ? `✓ ${selectedStock} unidades disponibles para esta variante`
                  : '✗ Variante sin stock — selecciona otra'}
              </div>
            </>
          )}

          <button
            className="btn btn-primary btn-full btn-lg"
            onClick={addToCart}
            disabled={adding || !selectedVariant || selectedStock <= 0}
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

          {/* Perks */}
          <div className="perks-row">
            <div className="perk-item"><Truck size={16} /> Envío seguro</div>
            <div className="perk-item"><Shield size={16} /> Compra protegida</div>
            <div className="perk-item"><RotateCcw size={16} /> Cambios fáciles</div>
          </div>
        </section>

        {/* Reviews */}
        <section className="reviews-panel">
          <div className="section-heading">
            <h2>Reseñas de clientes</h2>
            {product.reviews_count > 0 && (
              <span style={{ color: 'var(--neutral-500)', fontSize: '0.875rem' }}>
                {product.reviews_count} reseña(s) · promedio {Number(product.average_rating || 0).toFixed(1)}/5
              </span>
            )}
          </div>
          {data.reviews.length === 0 ? (
            <div className="state">Aún no hay reseñas. Las reseñas se habilitan después de recibir el producto.</div>
          ) : (
            <div className="reviews-grid">
              {data.reviews.map((review) => (
                <article key={review.id} className="review-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <strong>{review.user_name}</strong>
                    <span style={{ fontSize: '0.7rem', color: 'var(--brand-600)', fontWeight: 700, background: 'var(--brand-50)', padding: '2px 8px', borderRadius: 99 }}>
                      ✓ Compra verificada
                    </span>
                  </div>
                  <div className="stars" style={{ fontSize: '0.9rem' }}>
                    {'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)}
                  </div>
                  <p style={{ margin: '0.4rem 0 0', color: 'var(--neutral-700)', fontSize: '0.875rem' }}>
                    {review.comment}
                  </p>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
