import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Star } from 'lucide-react';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useAsync } from '../hooks/useAsync';

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [variantId, setVariantId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [message, setMessage] = useState('');
  const { data, loading, error } = useAsync(async () => {
    const [product, reviews] = await Promise.all([api.get(`/products/${id}`), api.get(`/products/${id}/reviews`)]);
    return { product: product.data, reviews: reviews.data };
  }, [id]);

  const selectedVariant = useMemo(
    () => data?.product?.variants.find((variant) => String(variant.id) === String(variantId)),
    [data, variantId]
  );

  if (loading) return <div className="state">Cargando producto...</div>;
  if (error) return <div className="state error">{error}</div>;

  const product = data.product;
  const images = product.gallery?.length ? product.gallery : [{ id: 'main', image_url: product.image_url, alt_text: product.name }];

  const addToCart = async () => {
    setMessage('');
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    if (!selectedVariant || selectedVariant.stock < quantity) {
      setMessage('Selecciona una variante con stock suficiente.');
      return;
    }
    await api.post('/cart/items', { variant_id: selectedVariant.id, quantity });
    setMessage('Producto agregado al carrito.');
  };

  return (
    <main className="page-shell product-detail">
      <section className="product-gallery">
        <img className="detail-image" src={images[0].image_url} alt={images[0].alt_text || product.name} />
        <div className="thumb-row">
          {images.map((image) => (
            <img key={image.id} src={image.image_url} alt={image.alt_text || product.name} />
          ))}
        </div>
      </section>
      <section className="detail-panel">
        <span className="category-chip">{product.category_name}</span>
        <h1>{product.name}</h1>
        <p>{product.long_description || product.description}</p>
        <div className="rating-row">
          <Star size={18} fill="currentColor" />
          <strong>{product.average_rating || 0}</strong>
          <span>({product.reviews_count} resenas)</span>
        </div>
        <strong className="detail-price">${Number(product.base_price).toLocaleString('es-CO')}</strong>
        <label>
          Variante
          <select value={variantId} onChange={(event) => setVariantId(event.target.value)} required>
            <option value="">Selecciona talla, color o SKU</option>
            {product.variants.map((variant) => (
              <option key={variant.id} value={variant.id} disabled={variant.stock <= 0}>
                {variant.sku} | {variant.color || 'sin color'} | {variant.size || variant.custom_attribute || 'unica'} | stock {variant.stock}
              </option>
            ))}
          </select>
        </label>
        <label>
          Cantidad
          <input
            type="number"
            min="1"
            max={selectedVariant?.stock || 1}
            value={quantity}
            onChange={(event) => setQuantity(Number(event.target.value))}
          />
        </label>
        {selectedVariant ? (
          <p className={selectedVariant.stock > 0 ? 'alert success' : 'alert error'}>
            {selectedVariant.stock > 0 ? 'Variante disponible para agregar al carrito.' : 'Variante sin stock.'}
          </p>
        ) : (
          <p className="alert">Selecciona una variante disponible para continuar.</p>
        )}
        {message && <p className={message.includes('agregado') ? 'alert success' : 'alert error'}>{message}</p>}
        <button className="primary-button" onClick={addToCart}>Agregar al carrito</button>
      </section>
      <section className="reviews-panel">
        <h2>Resenas</h2>
        {data.reviews.map((review) => (
          <article key={review.id} className="review-card">
            <strong>{review.user_name}</strong>
            <span>{'★'.repeat(review.rating)}</span>
            <p>{review.comment}</p>
          </article>
        ))}
        {data.reviews.length === 0 && <p>No hay resenas publicadas todavia.</p>}
      </section>
    </main>
  );
}
