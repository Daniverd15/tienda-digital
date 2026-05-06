import { Link, NavLink } from 'react-router-dom';
import { LogOut, ShoppingBag, UserRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Navbar() {
  const { user, isAdmin, logout } = useAuth();

  return (
    <header className="topbar">
      <Link to="/" className="brand">
        <span className="brand-mark">TD</span>
        Tienda Digital
      </Link>
      <nav className="nav-links" aria-label="Navegacion principal">
        <NavLink to="/catalogo">Catalogo</NavLink>
        {user && <NavLink to="/carrito">Carrito</NavLink>}
        {user && <NavLink to="/mis-pedidos">Mis pedidos</NavLink>}
        {isAdmin && <NavLink to="/admin">Admin</NavLink>}
      </nav>
      <div className="nav-actions">
        {user ? (
          <>
            <span className="session-pill">
              <UserRound size={16} />
              {user.name}
            </span>
            <button className="icon-button" onClick={logout} title="Cerrar sesion" aria-label="Cerrar sesion">
              <LogOut size={18} />
            </button>
          </>
        ) : (
          <>
            <Link className="ghost-link" to="/login">Ingresar</Link>
            <Link className="button-link" to="/registro">
              <ShoppingBag size={16} />
              Crear cuenta
            </Link>
          </>
        )}
      </div>
    </header>
  );
}

