import { Link } from 'react-router-dom';
import api from '../api/client';
import ProductCard from '../components/ProductCard';
import { useAsync } from '../hooks/useAsync';

export default function Home() {
  const { data, loading, error } = useAsync(async () => {
    const [settings, messages, categories, products] = await Promise.all([
      api.get('/store/settings'),
      api.get('/store/messages'),
      api.get('/categories'),
      api.get('/products')
    ]);
    return {
      settings: settings.data,
      messages: messages.data,
      categories: categories.data,
      products: products.data.slice(0, 3)
    };
  }, []);

  if (loading) return <div className="state">Cargando tienda...</div>;
  if (error) return <div className="state error">{error}</div>;

  const settings = data.settings || {};

  return (
    <main>
      <section
        className="hero"
        style={{
          '--brand-primary': settings.primary_color || '#1f7a5c',
          backgroundImage: `linear-gradient(90deg, rgba(23,32,38,.78), rgba(23,32,38,.26)), url(${settings.banner_url || 'https://images.unsplash.com/photo-1441986300917-64674bd600d8'})`
        }}
      >
        <div className="hero-content">
          <span className="eyebrow">{settings.currency || 'COP'} | Compra local</span>
          <h1>{settings.commercial_name || 'Tienda Digital Scrum'}</h1>
          <p>Catalogo activo, inventario visible, checkout con pagos simulados y seguimiento de pedidos.</p>
          <Link className="hero-button" to="/catalogo">Explorar catalogo</Link>
        </div>
      </section>

      <section className="content-band">
        <div className="message-grid">
          {data.messages.map((message) => (
            <article key={message.id} className={`message-card ${message.type}`}>
              <strong>{message.title}</strong>
              <p>{message.content}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="content-band">
        <div className="section-heading">
          <h2>Categorias activas</h2>
          <Link to="/catalogo">Ver todos</Link>
        </div>
        <div className="category-grid">
          {data.categories.map((category) => (
            <Link key={category.id} className="category-tile" to={`/catalogo?categoria=${category.id}`}>
              <strong>{category.name}</strong>
              <span>{category.description}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="content-band">
        <div className="section-heading">
          <h2>Productos destacados</h2>
          <Link to="/catalogo">Comprar ahora</Link>
        </div>
        <div className="product-grid">
          {data.products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </section>
    </main>
  );
}

