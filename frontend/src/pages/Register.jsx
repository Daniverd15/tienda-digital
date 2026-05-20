/**
 * Pagina de Registro (/registro).
 *
 * Formulario para crear cuenta de cliente nuevo. Valida en cliente y en
 * servidor:
 *  - Email unico (case-insensitive)
 *  - Contrasena fuerte (>=8, mayus, minus, digito, simbolo)
 *  - Telefono numerico
 *
 * Tras registro exitoso: persiste tokens, hace auto-login y redirige al
 * catalogo. El backend ademas envia un correo de bienvenida via SMTP.
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ShieldCheck, UserPlus } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function Register() {
  const { register } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', phone: '', password: '' });
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register(form);
      toast('¡Cuenta creada exitosamente!', 'success', 'Bienvenido');
      navigate('/catalogo', { replace: true });
    } catch (err) {
      toast(err.response?.data?.detail || 'No se pudo crear la cuenta.', 'error', 'Error de registro');
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
        <h1>Crear cuenta</h1>
        <p className="auth-sub">Únete y empieza a comprar en segundos.</p>

        <label>
          Nombre completo *
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Tu nombre"
            autoComplete="name"
            required
          />
        </label>
        <label>
          Correo electrónico *
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
          Teléfono
          <input
            type="tel"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="+57 300 000 0000"
            autoComplete="tel"
          />
        </label>
        <label>
          Contraseña *
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="Mín. 8 caracteres, mayúscula y número"
            autoComplete="new-password"
            required
            minLength={8}
          />
        </label>

        <button className="btn btn-primary btn-full" style={{ marginTop: '0.75rem' }} disabled={loading}>
          <UserPlus size={16} />
          {loading ? 'Creando cuenta…' : 'Registrarme'}
        </button>

        <div className="auth-footer">
          ¿Ya tienes cuenta? <Link to="/login">Inicia sesión</Link>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '1rem', fontSize: '0.78rem', color: 'var(--neutral-400)' }}>
          <ShieldCheck size={13} /> Tu información está segura y encriptada
        </div>
      </form>
    </section>
  );
}
