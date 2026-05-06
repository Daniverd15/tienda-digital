import { Link } from 'react-router-dom';
import { PackageCheck } from 'lucide-react';

export default function ProductCard({ product }) {
  return (
    <article className="product-card">
      <img src={product.image_url || 'https://images.unsplash.com/photo-1523381294911-8d3cead13475'} alt={product.name} />
      <div className="product-card-body">
        <span className="category-chip">{product.category_name}</span>
        <h3>{product.name}</h3>
        <p>{product.description}</p>
        <div className="product-meta">
          <strong>${Number(product.base_price).toLocaleString('es-CO')}</strong>
          <span>
            <PackageCheck size={15} />
            {product.stock} disponibles
          </span>
        </div>
        <Link className="button-link product-action" to={`/productos/${product.id}`}>
          Ver detalle
        </Link>
      </div>
    </article>
  );
}

