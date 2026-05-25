import { Link } from 'react-router-dom';
import { useAsync } from '../hooks/useAsync';
import api from '../api/client';

export default function Footer() {
  const { data: settings } = useAsync(() => api.get('/store/settings').then((r) => r.data), []);
  const name = settings?.commercial_name || 'Distrito Urbano';
  const year = new Date().getFullYear();

  return (
    <footer className="site-footer">
      <div className="footer-grid">
        <div className="footer-brand">
          <strong>{name}</strong>
          <p>Tienda digital con catálogo, carrito, pagos y seguimiento de pedidos en tiempo real.</p>
        </div>
        <div className="footer-col">
          <h4>Tienda</h4>
          <Link to="/catalogo">Catálogo</Link>
          <Link to="/mis-pedidos">Mis pedidos</Link>
          <Link to="/notificaciones">Notificaciones</Link>
        </div>
        <div className="footer-col">
          <h4>Cuenta</h4>
          <Link to="/login">Iniciar sesión</Link>
          <Link to="/registro">Crear cuenta</Link>
        </div>
        <div className="footer-col">
          <h4>Contacto</h4>
          {settings?.contact_email && <a href={`mailto:${settings.contact_email}`}>{settings.contact_email}</a>}
          {settings?.contact_phone && <a href={`tel:${settings.contact_phone}`}>{settings.contact_phone}</a>}
        </div>
      </div>
      <div className="footer-bottom">
        <span>© {year} {name}. Todos los derechos reservados.</span>
        <span>Ingeniería de Software · Scrum Demo Project</span>
      </div>
    </footer>
  );
}
