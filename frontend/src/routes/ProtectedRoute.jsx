/**
 * Componente de ruta protegida. Envuelve rutas que requieren autenticacion.
 *
 * ============================================================================
 * USO
 * ============================================================================
 * En App.jsx se usa con React Router v6 como envoltorio de rutas:
 *
 *   <Route element={<ProtectedRoute />}>
 *     <Route path="/mis-pedidos" element={<MyOrders />} />
 *   </Route>
 *
 *   <Route element={<ProtectedRoute role="admin" />}>
 *     <Route path="/admin" element={<AdminHome />} />
 *   </Route>
 *
 * El <Outlet /> de react-router-dom renderiza la ruta hija (MyOrders,
 * AdminHome, etc.) cuando los chequeos pasan.
 *
 * ============================================================================
 * COMPORTAMIENTO
 * ============================================================================
 * - Si loading=true (revalidando token con /auth/me) → muestra mensaje.
 * - Si no autenticado → redirige a /login, pasando location.from para que
 *   el Login pueda volver a la ruta solicitada despues del login exitoso.
 * - Si la ruta requiere admin y el user no es admin → redirige a / (home).
 *   Esto IMPIDE que un customer acceda a /admin con URL directa.
 * - Si todo OK → renderiza la ruta hija via <Outlet />.
 */
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ role }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();
  const location = useLocation();

  // Mientras AuthContext revalida el token (al cargar la SPA), mostramos
  // un mensaje. Sin esto, redirigiriamos a /login antes de saber si el
  // usuario tenia sesion valida (mala UX al refrescar la pagina).
  if (loading) {
    return <div className="state">Validando sesion...</div>;
  }

  // No autenticado: redirige a /login.
  // Pasamos `state={{ from: location }}` para que el Login pueda redirigir
  // de vuelta a la ruta solicitada despues del login exitoso (UX comun).
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // Autenticado pero la ruta requiere admin y el user es customer:
  // redirigimos al home publico (no a /login porque ya esta logueado).
  if (role === 'admin' && !isAdmin) {
    return <Navigate to="/" replace />;
  }

  // Chequeos OK: renderizar la ruta hija (Outlet de React Router v6).
  return <Outlet />;
}
