import { Link } from 'react-router-dom';

const modules = [
  ['Pedidos', '/admin/pedidos'],
  ['Catalogo e inventario', '/admin/catalogo'],
  ['Finanzas', '/admin/finanzas'],
  ['Configuracion', '/admin/configuracion'],
  ['Auditoria', '/admin/auditoria']
];

export default function AdminHome() {
  return (
    <main className="page-shell">
      <span className="eyebrow">Panel administrativo</span>
      <h1>Operacion de la tienda</h1>
      <div className="category-grid">
        {modules.map(([label, href]) => (
          <Link className="category-tile" to={href} key={href}>
            <strong>{label}</strong>
            <span>Gestionar modulo</span>
          </Link>
        ))}
      </div>
    </main>
  );
}

