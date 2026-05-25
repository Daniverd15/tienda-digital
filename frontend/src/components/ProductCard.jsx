import { Link } from 'react-router-dom';
import { Package, Star } from 'lucide-react';
import { assetUrl } from '../utils/assets';

export default function ProductCard({ product }) {
  const image = assetUrl(product.image_url) || 'https://images.unsplash.com/photo-1523381294911-8d3cead13475?w=600&q=80';
  const price = Number(product.base_price || 0).toLocaleString('es-CO');
  const inventoryAvailable = product.inventory_available !== false;
  const variantCount = Number(product.variant_count || 0);
  const stock = Number(product.stock || 0);

  // Tres estados desde la perspectiva del cliente:
  //   - Inventory caido (inventoryAvailable=false): no podemos confirmar el
  //     stock; mostramos "Consultar" sin overlay para no marcarlo como
  //     agotado falsamente.
  //   - Inventory OK pero (sin variantes O stock=0): el cliente NO puede
  //     comprarlo, asi que va el efecto AGOTADO completo (grayscale + sello).
  //   - Inventory OK + stock > 0: producto disponible, sin overlay.
  const isOutOfStock = inventoryAvailable && (variantCount === 0 || stock <= 0);
  const isLowStock = inventoryAvailable && variantCount > 0 && stock > 0 && stock <= 5;

  return (
    <article className={`product-card${isOutOfStock ? ' product-card-out' : ''}`}>
      <div className="product-card-img">
        <img src={image} alt={product.name} loading="lazy" />
        {isOutOfStock && (
          <div className="card-badge card-badge-out">
            <span className="card-badge-label">AGOTADO</span>
          </div>
        )}
        {!isOutOfStock && isLowStock && (
          <div className="card-badge card-badge-low">
            Últimas {stock} uds
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
            {!inventoryAvailable ? (
              <>
                <Package size={13} />
                Consultar
              </>
            ) : isOutOfStock ? (
              <span style={{ color: 'var(--error-text)', fontWeight: 700 }}>Sin stock</span>
            ) : (
              <>
                <Package size={13} />
                {stock} disponibles
              </>
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
          className={`btn ${isOutOfStock ? 'btn-secondary' : 'btn-primary'}`}
          style={{ marginTop: '0.5rem' }}
          to={`/productos/${product.id}`}
        >
          {isOutOfStock ? 'Ver producto' : 'Ver detalle'}
        </Link>
      </div>
    </article>
  );
}
