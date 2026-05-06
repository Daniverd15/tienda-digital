import {
  BarChart2,
  BookOpen,
  ChevronRight,
  ClipboardList,
  Cog,
  FileText,
  LayoutDashboard,
  LogOut,
  Package,
  ShoppingBag,
  Users,
} from 'lucide-react';
import { NavLink, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

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
      { to: '/admin/auditoria',     icon: <BookOpen size={16} />,      label: 'Bitácora' },
    ],
  },
];

export default function AdminLayout({ children }) {
  const { user, logout } = useAuth();

  const initials = user?.name
    ? user.name.split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase()
    : 'AD';

  return (
    <div className="admin-shell">
      {/* Sidebar */}
      <aside className="admin-sidebar">
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

      {/* Main */}
      <div className="admin-content">
        {children}
      </div>
    </div>
  );
}
