/**
 * Pagina del catalogo publico (/catalogo).
 *
 * Muestra la grilla de productos disponibles con filtros: busqueda por texto,
 * categoria, rango de precio y "solo con stock". El filtro de stock se aplica
 * en cliente sobre los datos que devuelve /api/products (que ya trae el
 * campo `stock` enriquecido desde Inventory por el Catalog Service).
 *
 * Soporta deep-link por categoria: /catalogo?categoria=3 selecciona la
 * categoria automaticamente.
 *
 * Renderiza con <ProductCard> que muestra el overlay AGOTADO con efecto
 * grisaceo cuando inventory_available=true && stock=0.
 */
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
    const [categories, products] = await Promise.all([api.get('/categories'), api.get('/products')]);
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
    // Solo enviamos al backend los filtros que entiende; in_stock se aplica
    // en cliente porque el endpoint /products no acepta ese parametro.
    const { in_stock, ...serverFilters } = filters;
    const query = Object.fromEntries(
      Object.entries(serverFilters).filter(([, value]) => value !== '' && value !== false)
    );
    try {
      const { data: result } = await api.get('/products', { params: query });
      setProducts(result);
    } finally {
      setSearching(false);
    }
  };

  // Filtro cliente de "Con stock": un producto cuenta con stock si Inventory
  // confirmo que tiene al menos 1 unidad disponible.
  const visibleProducts = filters.in_stock
    ? products.filter((p) => (p.inventory_available !== false) && Number(p.stock || 0) > 0)
    : products;

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
        {visibleProducts.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
      {visibleProducts.length === 0 && (
        <p className="state">
          {filters.in_stock
            ? 'No hay productos con stock disponible. Desmarca el filtro "Con stock" para ver el resto del catálogo.'
            : 'No hay productos activos en esta categoría.'}
        </p>
      )}
    </main>
  );
}
