/**
 * Pagina Home / Landing publica (/).
 *
 * Carga el overview del catalogo via GET /catalog (cacheado en Redis):
 *  - Configuracion visual (logo, banner, colores)
 *  - Mensajes informativos activos (avisos, promos)
 *  - Categorias activas con sus links a /catalogo?categoria=X
 *  - 6 productos destacados (los mas recientes publicados)
 *
 * Sirve como punto de entrada para visitantes anonimos. Tiene CTAs visibles
 * al catalogo completo y al login/registro.
 */
import { Link } from 'react-router-dom';
import { ArrowRight, Package, ShieldCheck, Star, Truck, Zap } from 'lucide-react';
import api from '../api/client';
import ProductCard from '../components/ProductCard';
import { useAsync } from '../hooks/useAsync';
import { assetUrl } from '../utils/assets';

const FEATURES = [
  { icon: <Truck size={20} />, title: 'Envío a toda Colombia', sub: 'Calculamos el costo al momento' },
  { icon: <ShieldCheck size={20} />, title: 'Compra protegida', sub: 'Pagos seguros y encriptados' },
  { icon: <Zap size={20} />, title: 'Entrega rápida', sub: 'Preparación en 24 horas' },
  { icon: <Package size={20} />, title: 'Devoluciones fáciles', sub: '15 días para cambios' },
];

export default function Home() {
  const { data, loading, error } = useAsync(async () => {
    const [settings, messages, categories, products] = await Promise.all([
      api.get('/store/settings'),
      api.get('/store/messages'),
      api.get('/categories'),
      api.get('/products'),
    ]);
    return {
      settings: settings.data,
      messages: messages.data,
      categories: categories.data,
      products: products.data.slice(0, 3),
    };
  }, []);

  if (loading) {
    return (
      <div>
        <div style={{ minHeight: 'min(80vh,720px)', background: 'var(--neutral-200)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
          <div className="skeleton" style={{ width: 300, height: 40, borderRadius: 8 }} />
        </div>
      </div>
    );
  }

  if (error) return <div className="state error">Error al cargar la tienda.</div>;

  const { settings, messages, categories, products } = data;
  const primaryColor = settings?.primary_color || '#1f7a5c';
  const banner = assetUrl(settings?.banner_url) || 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1600&q=80';

  return (
    <>
      {/* Hero */}
      <section
        className="hero"
        style={{ backgroundImage: `url(${banner})` }}
      >
        <div className="hero-overlay" />
        <div className="hero-content">
          <span className="hero-eyebrow">
            <Star size={12} />
            {settings?.currency || 'COP'} · Compra local
          </span>
          <h1>{settings?.commercial_name || 'Tienda Digital'}</h1>
          <p>Descubre nuestro catálogo curado con las mejores prendas urbanas. Stock en tiempo real, pagos seguros y seguimiento de pedido.</p>
          <div className="hero-cta-row">
            <Link className="hero-btn-primary" to="/catalogo">
              Explorar catálogo <ArrowRight size={18} />
            </Link>
            <Link className="hero-btn-ghost" to="/registro">
              Crear cuenta gratis
            </Link>
          </div>
        </div>
      </section>

      {/* Features bar */}
      <div className="content-band" style={{ paddingTop: '1.5rem', paddingBottom: '1.5rem' }}>
        <div className="features-row">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature-item">
              <div className="feature-icon">{f.icon}</div>
              <div className="feature-text">
                <strong>{f.title}</strong>
                <span>{f.sub}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Informative messages */}
      {messages.length > 0 && (
        <div className="content-band" style={{ paddingTop: '1rem', paddingBottom: '1rem' }}>
          <div className="message-grid">
            {messages.map((msg) => (
              <article key={msg.id} className={`message-card ${msg.type}`}>
                <strong>{msg.title}</strong>
                <p>{msg.content}</p>
              </article>
            ))}
          </div>
        </div>
      )}

      {/* Categories */}
      <div className="content-band">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Explora</span>
            <h2>Categorías activas</h2>
          </div>
          <Link to="/catalogo">Ver todo <ArrowRight size={14} /></Link>
        </div>
        <div className="category-grid">
          {categories.map((cat) => (
            <Link key={cat.id} className="category-tile" to={`/catalogo?categoria=${cat.id}`}>
              <div className="cat-icon">
                <Package size={20} />
              </div>
              <strong>{cat.name}</strong>
              <span>{cat.description || 'Explorar productos'}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* Featured products */}
      <div className="content-band-alt">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Lo más nuevo</span>
            <h2>Productos destacados</h2>
          </div>
          <Link to="/catalogo">Ver catálogo completo <ArrowRight size={14} /></Link>
        </div>
        <div className="product-grid">
          {products.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
        {products.length === 0 && (
          <div className="state">El catálogo se está preparando. Vuelve pronto.</div>
        )}
      </div>

      {/* CTA strip */}
      <section
        style={{
          background: primaryColor,
          padding: 'clamp(2rem,5vw,4rem) clamp(1rem,5vw,4rem)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '2rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ color: '#fff' }}>
          <h2 style={{ fontSize: 'clamp(1.5rem,4vw,2.25rem)', fontWeight: 900, margin: '0 0 0.5rem', letterSpacing: '-0.02em' }}>
            ¿Listo para comprar?
          </h2>
          <p style={{ margin: 0, opacity: 0.8, fontSize: '1rem' }}>Regístrate, agrega al carrito y paga en segundos.</p>
        </div>
        <Link
          to="/registro"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.9rem 2rem',
            background: 'var(--accent-500)',
            color: 'var(--neutral-900)',
            borderRadius: 'var(--radius-lg)',
            fontWeight: 800,
            fontSize: '0.9375rem',
            textDecoration: 'none',
            flexShrink: 0,
          }}
        >
          Crear cuenta gratis <ArrowRight size={18} />
        </Link>
      </section>
    </>
  );
}
