/**
 * Context de autenticacion: gestiona la sesion del usuario en toda la SPA.
 *
 * ============================================================================
 * PROPOSITO
 * ============================================================================
 * Provee a TODOS los componentes hijos:
 *   - user:            objeto del usuario logueado (o null)
 *   - isAuthenticated: boolean conveniente
 *   - isAdmin:         boolean conveniente para mostrar rutas admin
 *   - loading:         true mientras revalidamos el token al montar
 *   - login, register, logout: funciones para gestionar la sesion
 *
 * Cualquier componente puede consumirlo con `const { user } = useAuth()`.
 *
 * ============================================================================
 * PERSISTENCIA EN localStorage
 * ============================================================================
 * - td_token: access_token JWT (lo lee api/client.js para inyectar header)
 * - td_user:  snapshot del usuario para no esperar /auth/me al montar
 *
 * Al montar el provider, si hay token guardado, llamamos a /auth/me para
 * verificar que sigue valido. Si falla (401), hacemos logout (limpieza).
 *
 * Nota: localStorage es vulnerable a XSS. Para el MVP academico es
 * aceptable; en produccion seria mejor usar httpOnly cookies.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import api from '../api/client';

// El context arranca en null; el provider lo "rellena" con el value real.
// Si algun componente intenta useAuth() fuera del provider, lanzamos error.
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // Inicializamos user con lo que haya en localStorage para evitar parpadeo
  // (la primera renderizacion ya tiene el usuario si la sesion estaba viva).
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem('td_user');
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(false);

  // Al montar el provider, verificamos si el token sigue valido contra el backend.
  // Si /auth/me responde 401 (token expirado o revocado), hacemos logout silencioso.
  useEffect(() => {
    const token = localStorage.getItem('td_token');
    if (!token) return;
    setLoading(true);
    api
      .get('/auth/me')
      .then(({ data }) => {
        // Token valido: actualizamos el snapshot del usuario por si cambio
        // algun dato (ej. el admin promovio al user a admin).
        setUser(data);
        localStorage.setItem('td_user', JSON.stringify(data));
      })
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, []);

  /**
   * Persiste el par token + user al hacer login/register exitoso.
   * Centraliza para mantener consistencia entre los dos flujos.
   */
  const persistSession = (data) => {
    localStorage.setItem('td_token', data.access_token);
    localStorage.setItem('td_user', JSON.stringify(data.user));
    setUser(data.user);
  };

  /**
   * Login: envia credenciales al backend, persiste tokens y actualiza el state.
   * Devuelve el user para que el caller pueda redirigir segun el role
   * (admin → /admin, customer → /catalogo).
   */
  const login = async (credentials) => {
    const { data } = await api.post('/auth/login', credentials);
    persistSession(data);
    return data.user;
  };

  /**
   * Register: crea cuenta nueva y persiste tokens (auto-login).
   * El backend valida fortaleza de contrasena y unicidad de email.
   */
  const register = async (payload) => {
    const { data } = await api.post('/auth/register', payload);
    persistSession(data);
    return data.user;
  };

  /**
   * Logout: revoca tokens en backend + limpia localStorage + actualiza state.
   * El bloque try/catch permite cerrar sesion local aunque el backend no responda
   * (ej. red intermitente). Defensa: el cliente SIEMPRE termina logueado out.
   */
  const logout = async () => {
    try {
      if (localStorage.getItem('td_token')) {
        await api.post('/auth/logout');
      }
    } catch {
      // El backend registra el cierre cuando es posible; el cliente siempre
      // limpia la sesion local.
    } finally {
      localStorage.removeItem('td_token');
      localStorage.removeItem('td_user');
      setUser(null);
    }
  };

  // useMemo evita recrear el value en cada render (importante: el provider
  // re-renderizaria a TODOS los consumidores si value cambia de referencia).
  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      isAdmin: user?.role === 'admin',
      login,
      register,
      logout
    }),
    [user, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook conveniente: `const { user, login, logout } = useAuth()`.
 * Lanza error si se usa fuera del provider (ayuda a debuggear).
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de AuthProvider');
  }
  return context;
}
