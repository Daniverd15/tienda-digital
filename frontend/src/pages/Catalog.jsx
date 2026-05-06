import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../api/client';
import ProductCard from '../components/ProductCard';
import { useAsync } from '../hooks/useAsync';

export default function Catalog() {
  const [params] = useSearchParams();
  const selectedCategory = params.get('categoria');
  const [filters, setFilters] = useState({
    q: '',
    category_id: selectedCategory || '',
    min_price: '',
    max_price: '',
    in_stock: false
  });
  const [products, setProducts] = useState([]);
  const [searching, setSearching] = useState(false);
  const { data, loading, error } = useAsync(async () => {
    const [categories, products] = await Promise.all([api.get('/categories'), api.get('/products/search')]);
    return { categories: categories.data, products: products.data };
  }, []);

  useEffect(() => {
    if (data?.products) setProducts(data.products);
  }, [data]);

  useEffect(() => {
    setFilters((current) => ({ ...current, category_id: selectedCategory || '' }));
  }, [selectedCategory]);

  const onSearch = async (event) => {
    event.preventDefault();
    setSearching(true);
    const query = Object.fromEntries(
      Object.entries(filters).filter(([, value]) => value !== '' && value !== false)
    );
    try {
      const { data: result } = await api.get('/products/search', { params: query });
      setProducts(result);
    } finally {
      setSearching(false);
    }
  };

  if (loading) return <div className="state">Cargando catalogo...</div>;
  if (error) return <div className="state error">{error}</div>;

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
      <form className="catalog-search" onSubmit={onSearch}>
        <input
          placeholder="Buscar camiseta, gorra, tenis..."
          value={filters.q}
          onChange={(event) => setFilters({ ...filters, q: event.target.value })}
        />
        <select
          value={filters.category_id}
          onChange={(event) => setFilters({ ...filters, category_id: event.target.value })}
        >
          <option value="">Todas las categorias</option>
          {data.categories.map((category) => (
            <option key={category.id} value={category.id}>{category.name}</option>
          ))}
        </select>
        <input
          type="number"
          min="0"
          placeholder="Precio minimo"
          value={filters.min_price}
          onChange={(event) => setFilters({ ...filters, min_price: event.target.value })}
        />
        <input
          type="number"
          min="0"
          placeholder="Precio maximo"
          value={filters.max_price}
          onChange={(event) => setFilters({ ...filters, max_price: event.target.value })}
        />
        <label className="check-inline">
          <input
            type="checkbox"
            checked={filters.in_stock}
            onChange={(event) => setFilters({ ...filters, in_stock: event.target.checked })}
          />
          Con stock
        </label>
        <button className="btn btn-primary" style={{ margin: 0, width: 'auto' }} disabled={searching}>{searching ? 'Buscando…' : 'Buscar'}</button>
      </form>
      <div className="product-grid">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
      {products.length === 0 && <p className="state">No hay productos activos en esta categoria.</p>}
    </main>
  );
}
