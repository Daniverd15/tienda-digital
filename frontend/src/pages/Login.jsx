import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { LogIn, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function Login() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const user = await login(form);
      toast(`Bienvenido, ${user.name}!`, 'success');
      const fallback = user.role === 'admin' ? '/admin' : '/catalogo';
      navigate(location.state?.from?.pathname || fallback, { replace: true });
    } catch (err) {
      toast(err.response?.data?.detail || 'Credenciales incorrectas.', 'error', 'Error de acceso');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="auth-logo">
          <span className="brand-mark">DU</span>
          <strong>Distrito Urbano</strong>
        </div>
        <h1>Iniciar sesión</h1>
        <p className="auth-sub">Bienvenido de vuelta. Ingresa tus credenciales.</p>

        <label>
          Correo electrónico
          <input
            type="email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="tu@email.com"
            autoComplete="email"
            required
          />
        </label>
        <label>
          Contraseña
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />
        </label>

        <button className="btn btn-primary btn-full" style={{ marginTop: '0.75rem' }} disabled={loading}>
          <LogIn size={16} />
          {loading ? 'Validando…' : 'Entrar'}
        </button>

        <div className="auth-footer">
          ¿No tienes cuenta? <Link to="/registro">Regístrate</Link>
        </div>

        <div className="auth-divider">Credenciales de prueba</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
          {[
            { label: 'Cliente',       email: 'cliente@tienda.com', pw: 'Cliente123*' },
            { label: 'Administrador', email: 'admin@tienda.com',   pw: 'Admin123*' },
          ].map((cred) => (
            <button
              key={cred.label}
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setForm({ email: cred.email, password: cred.pw })}
              style={{ flexDirection: 'column', gap: 2, height: 'auto', padding: '0.5rem' }}
            >
              <strong style={{ fontSize: '0.75rem' }}>{cred.label}</strong>
              <span style={{ fontSize: '0.7rem', color: 'var(--neutral-500)', fontWeight: 400 }}>{cred.email}</span>
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '1rem', fontSize: '0.78rem', color: 'var(--neutral-400)' }}>
          <ShieldCheck size={13} /> Tus datos están protegidos con cifrado
        </div>
      </form>
    </section>
  );
}
