import { Link } from 'react-router-dom';
import { Package, Star } from 'lucide-react';
import { assetUrl } from '../utils/assets';

export default function ProductCard({ product }) {
  const image = assetUrl(product.image_url) || 'https://images.unsplash.com/photo-1523381294911-8d3cead13475?w=600&q=80';
  const price = Number(product.base_price || 0).toLocaleString('es-CO');
  const inStock = (product.stock || 0) > 0;

  return (
    <article className="product-card">
      <div className="product-card-img">
        <img src={image} alt={product.name} loading="lazy" />
        {!inStock && (
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(23,32,38,0.55)',
            display: 'grid',
            placeItems: 'center',
            color: '#fff',
            fontWeight: 800,
            fontSize: '0.875rem',
            letterSpacing: '0.05em',
          }}>
            AGOTADO
          </div>
        )}
      </div>
      <div className="product-card-body">
        <span className="category-chip">{product.category_name}</span>
        <h3>{product.name}</h3>
        <p>{product.description}</p>
        <div className="product-meta">
          <strong>${price}</strong>
          <span>
            {inStock ? (
              <>
                <Package size={13} />
                {product.stock} disponibles
              </>
            ) : (
              <span style={{ color: 'var(--error-text)', fontWeight: 700 }}>Sin stock</span>
            )}
          </span>
        </div>
        {product.average_rating > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#ca8a04', fontSize: '0.8125rem' }}>
            <Star size={12} fill="currentColor" />
            <strong>{product.average_rating}</strong>
            <span style={{ color: 'var(--neutral-400)' }}>({product.reviews_count})</span>
          </div>
        )}
        <Link
          className={`btn btn-primary ${!inStock ? 'btn-secondary' : ''}`}
          style={{ marginTop: '0.5rem' }}
          to={`/productos/${product.id}`}
        >
          {inStock ? 'Ver detalle' : 'Ver producto'}
        </Link>
      </div>
    </article>
  );
}
