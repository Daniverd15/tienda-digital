/**
 * Cliente Axios centralizado para hablar con el backend.
 *
 * ============================================================================
 * PROPOSITO
 * ============================================================================
 * Todas las paginas y componentes del frontend importan ESTE cliente para
 * hacer requests al backend. Centralizamos para:
 *   1. Configurar UNA sola vez el baseURL (gateway Nginx en puerto 80).
 *   2. Inyectar automaticamente el JWT en el header Authorization en cada
 *      request (interceptor de Axios).
 *   3. Permitir agregar logica transversal en el futuro (retry, refresh
 *      token, manejo global de 401, etc.) sin tocar las paginas.
 *
 * ============================================================================
 * baseURL
 * ============================================================================
 * Por defecto apunta a http://localhost/api (el API Gateway Nginx en
 * docker-compose). En desarrollo local con Vite, se puede sobrescribir
 * con la variable de entorno VITE_API_URL en .env.local:
 *   VITE_API_URL=http://localhost:8004  ← bypass del gateway, va directo a Commerce
 *
 * En produccion el VITE_API_URL deberia apuntar al dominio real con HTTPS.
 *
 * ============================================================================
 * INTERCEPTOR DE AUTORIZACION
 * ============================================================================
 * Cada request HTTP que sale del frontend pasa por el interceptor que:
 *   1. Lee el access_token de localStorage (clave 'td_token').
 *   2. Si existe, agrega el header `Authorization: Bearer <token>`.
 *   3. Si no existe, deja la request sin auth (los endpoints publicos
 *      como GET /products funcionan sin token).
 *
 * El token se guarda en localStorage al hacer login (AuthContext.login) y
 * se borra al hacer logout. Es vulnerable a XSS pero suficiente para el
 * MVP academico. En produccion se usaria httpOnly cookies + CSRF token.
 */
import axios from 'axios';

// Bloque 7 (Fase 2): el frontend consume el API Gateway Nginx
// (http://localhost/api) en vez del monolito en :8000.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost/api'
});

// Interceptor que se ejecuta ANTES de cada request HTTP.
// Le agrega el header Authorization si hay un token guardado.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('td_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
