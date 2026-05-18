import axios from 'axios';

// Bloque 7 (Fase 2): el frontend consume el API Gateway Nginx
// (http://localhost/api) en vez del monolito en :8000.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost/api'
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('td_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;

