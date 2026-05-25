import {
  BarChart2,
  BookOpen,
  ChevronRight,
  ClipboardList,
  Cog,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Package,
  ShoppingBag,
  Star,
  Users,
} from 'lucide-react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useAsync } from '../hooks/useAsync';
import api from '../api/client';

const NAV = [
  {
    label: 'Operación',
    items: [
      { to: '/admin',           icon: <LayoutDashboard size={16} />, label: 'Dashboard' },
      { to: '/admin/pedidos',   icon: <ClipboardList size={16} />,   label: 'Pedidos' },
      { to: '/admin/clientes',  icon: <Users size={16} />,            label: 'Clientes' },
    ],
  },
  {
    label: 'Catálogo',
    items: [
      { to: '/admin/catalogo',  icon: <Package size={16} />,          label: 'Productos' },
    ],
  },
  {
    label: 'Finanzas',
    items: [
      { to: '/admin/finanzas',  icon: <BarChart2 size={16} />,        label: 'Dashboard financiero' },
    ],
  },
  {
    label: 'Config',
    items: [
      { to: '/admin/configuracion', icon: <Cog size={16} />,          label: 'Configuración' },
      { to: '/admin/resenas',       icon: <Star size={16} />,          label: 'Reseñas' },
      { to: '/admin/auditoria',     icon: <BookOpen size={16} />,      label: 'Bitácora' },
    ],
  },
];

const PAGE_TITLES = {
  '/admin':                   'Dashboard',
  '/admin/pedidos':           'Pedidos',
  '/admin/clientes':          'Clientes',
  '/admin/catalogo':          'Catálogo e inventario',
  '/admin/finanzas':          'Finanzas',
  '/admin/configuracion':     'Configuración',
  '/admin/resenas':           'Reseñas',
  '/admin/auditoria':         'Bitácora de auditoría',
};

export default function AdminLayout({ children }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();

  const { data: settings } = useAsync(() =>
    api.get('/store/settings').then((r) => r.data).catch(() => null), []
  );

  const storeName = settings?.commercial_name || 'Distrito Urbano';
  const pageTitle = PAGE_TITLES[pathname] || 'Admin';

  const initials = user?.name
    ? user.name.split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase()
    : 'AD';

  return (
    <div className="admin-shell">
      {/* Sidebar */}
      <aside className="admin-sidebar">
        <Link to="/admin" className="sidebar-brand">
          <div className="sidebar-brand-mark">DU</div>
          <span className="sidebar-brand-name">{storeName}</span>
        </Link>

        {NAV.map((group) => (
          <div className="sidebar-section" key={group.label}>
            <div className="sidebar-label">{group.label}</div>
            {group.items.map(({ to, icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/admin'}
                className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
              >
                {icon}
                {label}
              </NavLink>
            ))}
          </div>
        ))}

        <div className="sidebar-bottom">
          <Link to="/" className="sidebar-link">
            <ShoppingBag size={16} />
            Ver tienda
          </Link>
          <button
            onClick={logout}
            className="sidebar-link"
            style={{ background: 'none', border: 'none', width: '100%', cursor: 'pointer' }}
          >
            <LogOut size={16} />
            Cerrar sesión
          </button>
          <div className="sidebar-user" style={{ marginTop: '0.5rem' }}>
            <div className="sidebar-user-avatar">{initials}</div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-name">{user?.name || 'Administrador'}</div>
              <div className="sidebar-user-role">Administrador</div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main area */}
      <div className="admin-main">
        {/* Top header */}
        <header className="admin-topbar-bar">
          <span className="admin-topbar-title">{pageTitle}</span>
          <div className="admin-topbar-right">
            <span style={{ fontSize: '0.8125rem', color: 'var(--neutral-500)' }}>
              {user?.name}
            </span>
            <div className="sidebar-user-avatar" style={{ width: 30, height: 30, fontSize: '0.7rem', background: 'var(--brand-500)' }}>
              {initials}
            </div>
          </div>
        </header>

        {/* Page content */}
        <div className="admin-content">
          {children}
        </div>

        {/* Footer */}
        <footer className="admin-footer-bar">
          <span>© {new Date().getFullYear()} {storeName} — Panel Administrativo</span>
          <span>Ingeniería de Software · Scrum</span>
        </footer>
      </div>
    </div>
  );
}
