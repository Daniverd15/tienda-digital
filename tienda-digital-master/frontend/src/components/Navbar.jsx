import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { LogOut, Menu, ShoppingBag, UserRound, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import api from '../api/client';

function useCartCount(isAuthenticated) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) { setCount(0); return; }
    api.get('/cart').then((r) => {
      const items = r.data?.items || [];
      setCount(items.reduce((s, i) => s + i.quantity, 0));
    }).catch(() => {});
  }, [isAuthenticated]);

  return count;
}

export default function Navbar() {
  const { user, isAdmin, logout, isAuthenticated } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const cartCount = useCartCount(isAuthenticated);

  // close mobile nav on route change
  useEffect(() => { setOpen(false); }, [location.pathname]);

  const isAdminRoute = location.pathname.startsWith('/admin');
  if (isAdminRoute) return null; // admin has its own sidebar

  return (
    <>
      <header className="topbar">
        {/* Brand */}
        <Link to="/" className="brand">
          <span className="brand-mark">DU</span>
          Distrito Urbano
        </Link>

        {/* Desktop nav */}
        <nav className="nav-links" aria-label="Navegación principal">
          <NavLink to="/catalogo">Catálogo</NavLink>
          {isAuthenticated && (
            <NavLink to="/carrito" className="nav-cart-badge">
              <ShoppingBag size={16} />
              Carrito
              {cartCount > 0 && <span className="cart-count">{cartCount > 9 ? '9+' : cartCount}</span>}
            </NavLink>
          )}
          {isAuthenticated && <NavLink to="/mis-pedidos">Mis pedidos</NavLink>}
          {isAdmin && <NavLink to="/admin">Panel admin</NavLink>}
        </nav>

        {/* Actions */}
        <div className="nav-actions">
          {user ? (
            <>
              <span className="session-pill">
                <UserRound size={15} />
                {user.name}
              </span>
              <button className="icon-button" onClick={logout} title="Cerrar sesión" aria-label="Cerrar sesión">
                <LogOut size={17} />
              </button>
            </>
          ) : (
            <>
              <Link className="ghost-link" to="/login">Ingresar</Link>
              <Link className="btn btn-primary btn-sm" to="/registro">
                Crear cuenta
              </Link>
            </>
          )}
          {/* Hamburger (mobile) */}
          <button
            className="hamburger"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? 'Cerrar menú' : 'Abrir menú'}
            aria-expanded={open}
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>

      {/* Mobile drawer */}
      <nav className={`mobile-nav ${open ? 'open' : ''}`} aria-label="Menú móvil">
        <NavLink to="/catalogo">Catálogo</NavLink>
        {isAuthenticated && (
          <NavLink to="/carrito">
            <ShoppingBag size={16} />
            Carrito {cartCount > 0 && `(${cartCount})`}
          </NavLink>
        )}
        {isAuthenticated && <NavLink to="/mis-pedidos">Mis pedidos</NavLink>}
        {isAuthenticated && <NavLink to="/notificaciones">Notificaciones</NavLink>}
        {isAdmin && <NavLink to="/admin">Panel admin</NavLink>}
        {user ? (
          <button
            onClick={logout}
            style={{ background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: '0.65rem 0.75rem', borderRadius: 6, color: 'var(--neutral-700)', fontWeight: 600, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: 8 }}
          >
            <LogOut size={16} /> Cerrar sesión
          </button>
        ) : (
          <>
            <NavLink to="/login">Ingresar</NavLink>
            <NavLink to="/registro">Crear cuenta</NavLink>
          </>
        )}
      </nav>
    </>
  );
}
