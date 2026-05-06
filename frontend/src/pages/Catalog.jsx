import { useSearchParams } from 'react-router-dom';
import api from '../api/client';
import ProductCard from '../components/ProductCard';
import { useAsync } from '../hooks/useAsync';

export default function Catalog() {
  const [params] = useSearchParams();
  const selectedCategory = params.get('categoria');
  const { data, loading, error } = useAsync(async () => {
    const [categories, products] = await Promise.all([api.get('/categories'), api.get('/products')]);
    return { categories: categories.data, products: products.data };
  }, []);

  if (loading) return <div className="state">Cargando catalogo...</div>;
  if (error) return <div className="state error">{error}</div>;

  const products = selectedCategory
    ? data.products.filter((product) => String(product.category_id) === selectedCategory)
    : data.products;

  return (
    <main className="page-shell">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Catalogo activo</span>
          <h1>Productos publicados</h1>
        </div>
      </div>
      <div className="filter-row" aria-label="Categorias activas">
        <a className={!selectedCategory ? 'filter-chip active' : 'filter-chip'} href="/catalogo">Todos</a>
        {data.categories.map((category) => (
          <a
            key={category.id}
            className={String(category.id) === selectedCategory ? 'filter-chip active' : 'filter-chip'}
            href={`/catalogo?categoria=${category.id}`}
          >
            {category.name}
          </a>
        ))}
      </div>
      <div className="product-grid">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
      {products.length === 0 && <p className="state">No hay productos activos en esta categoria.</p>}
    </main>
  );
}

