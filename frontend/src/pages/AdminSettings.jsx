import { useEffect, useRef, useState } from 'react';
import { ImagePlus, Megaphone, Palette, Phone, Settings, ShoppingBag, Trash2, Plus } from 'lucide-react';
import api from '../api/client';
import AdminLayout from '../components/AdminLayout';
import Badge from '../components/Badge';
import Modal from '../components/Modal';
import { useToast } from '../context/ToastContext';

const emptyMessage = { title: '', content: '', type: 'info', active: true, start_date: '', end_date: '' };

const TABS = [
  { id: 'store',    label: 'Tienda',               icon: <Settings size={15} /> },
  { id: 'messages', label: 'Mensajes informativos', icon: <Megaphone size={15} /> },
];

function ImageUploader({ value, onChange, label }) {
  const inputRef = useRef();
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const upload = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const { data } = await api.post('/admin/upload-image', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      onChange(data.url);
    } catch {
      onChange('');
    } finally { setUploading(false); }
  };

  const previewSrc = value
    ? (value.startsWith('/uploads/') ? `${apiBase}${value}` : value)
    : null;

  return (
    <label style={{ display: 'grid', gap: '0.3rem', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-700)', margin: '0.6rem 0' }}>
      {label}
      <div
        className={`img-upload-zone${drag ? ' drag-over' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files[0]); }}
      >
        <input ref={inputRef} type="file" accept="image/*" onChange={(e) => upload(e.target.files[0])} />
        {previewSrc ? (
          <>
            <img src={previewSrc} alt="preview" className="img-upload-preview" />
            <span style={{ fontSize: '0.78rem', color: 'var(--neutral-500)' }}>Haz clic o arrastra para cambiar</span>
          </>
        ) : (
          <div style={{ padding: '0.5rem', color: 'var(--neutral-400)' }}>
            <ImagePlus size={24} style={{ margin: '0 auto 0.4rem' }} />
            <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{uploading ? 'Subiendo…' : 'Haz clic o arrastra'}</div>
            <div style={{ fontSize: '0.72rem', marginTop: '0.2rem' }}>JPG, PNG o WebP</div>
          </div>
        )}
      </div>
    </label>
  );
}

export default function AdminSettings() {
  const toast = useToast();
  const [tab, setTab] = useState('store');
  const [settings, setSettings] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messageForm, setMessageForm] = useState(emptyMessage);
  const [msgModal, setMsgModal] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const [sR, mR] = await Promise.all([
      api.get('/admin/settings'),
      api.get('/admin/messages'),
    ]);
    setSettings(sR.data);
    setMessages(mR.data);
  };

  useEffect(() => { load(); }, []);

  const saveSettings = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.put('/admin/settings', settings);
      setSettings(data);
      // Apply colors immediately
      if (data.primary_color) {
        document.documentElement.style.setProperty('--brand-500', data.primary_color);
        document.documentElement.style.setProperty('--brand-600', data.primary_color);
        document.documentElement.style.setProperty('--brand-400', data.primary_color);
        document.documentElement.style.setProperty('--brand-50', data.primary_color + '18');
      }
      if (data.secondary_color) {
        document.documentElement.style.setProperty('--accent-500', data.secondary_color);
        document.documentElement.style.setProperty('--accent-400', data.secondary_color);
      }
      toast('Configuración guardada y tema aplicado.', 'success');
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al guardar configuración.', 'error');
    } finally { setSaving(false); }
  };

  const createMessage = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(messageForm).map(([k, v]) => [k, v === '' ? null : v])
      );
      await api.post('/admin/messages', payload);
      toast('Mensaje creado.', 'success');
      setMsgModal(false);
      setMessageForm(emptyMessage);
      load();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al crear mensaje.', 'error');
    } finally { setSaving(false); }
  };

  const deleteMessage = async (id) => {
    await api.delete(`/admin/messages/${id}`).catch(() => {});
    toast('Mensaje eliminado.', 'success');
    load();
  };

  if (!settings) return <AdminLayout><div className="state">Cargando configuración...</div></AdminLayout>;

  const set = (field, value) => setSettings({ ...settings, [field]: value });

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">RF-09</span>
          <h1 className="page-title">Configuración</h1>
        </div>
      </div>

      <div className="tabs-bar">
        {TABS.map((t) => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* ── Store settings ── */}
      {tab === 'store' && (
        <form onSubmit={saveSettings}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', alignItems: 'start' }}>

            {/* Identidad visual */}
            <div className="section-card">
              <div className="section-card-header">
                <Palette size={15} />
                <span className="section-card-title">Identidad visual</span>
              </div>
              <div className="section-card-body" style={{ display: 'grid', gap: '0.1rem' }}>
                <label>
                  Nombre comercial *
                  <input value={settings.commercial_name} onChange={(e) => set('commercial_name', e.target.value)} required />
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <label>
                    Color primario
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <input type="color" value={settings.primary_color} onChange={(e) => set('primary_color', e.target.value)} style={{ width: 44, height: 36, padding: '2px', cursor: 'pointer', flex: 'none' }} />
                      <input value={settings.primary_color} onChange={(e) => set('primary_color', e.target.value)} style={{ flex: 1 }} />
                    </div>
                  </label>
                  <label>
                    Color secundario
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <input type="color" value={settings.secondary_color} onChange={(e) => set('secondary_color', e.target.value)} style={{ width: 44, height: 36, padding: '2px', cursor: 'pointer', flex: 'none' }} />
                      <input value={settings.secondary_color} onChange={(e) => set('secondary_color', e.target.value)} style={{ flex: 1 }} />
                    </div>
                  </label>
                </div>
                <ImageUploader
                  label="Logo de la tienda"
                  value={settings.logo_url}
                  onChange={(url) => set('logo_url', url)}
                />
                <ImageUploader
                  label="Banner principal"
                  value={settings.banner_url}
                  onChange={(url) => set('banner_url', url)}
                />
              </div>
            </div>

            {/* Contacto + Comercio + Preview */}
            <div style={{ display: 'grid', gap: '1.25rem' }}>
              <div className="section-card">
                <div className="section-card-header">
                  <Phone size={15} />
                  <span className="section-card-title">Contacto y datos</span>
                </div>
                <div className="section-card-body" style={{ display: 'grid', gap: '0.1rem' }}>
                  <label>Email de contacto * <input type="email" value={settings.contact_email} onChange={(e) => set('contact_email', e.target.value)} required /></label>
                  <label>Teléfono * <input value={settings.contact_phone} onChange={(e) => set('contact_phone', e.target.value)} required /></label>
                  <label>Moneda * <input value={settings.currency} onChange={(e) => set('currency', e.target.value)} required /></label>
                </div>
              </div>

              <div className="section-card">
                <div className="section-card-header">
                  <ShoppingBag size={15} />
                  <span className="section-card-title">Inventario</span>
                </div>
                <div className="section-card-body">
                  <label>
                    Umbral de stock mínimo *
                    <input type="number" min="1" value={settings.stock_threshold} onChange={(e) => set('stock_threshold', Number(e.target.value))} required />
                  </label>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--neutral-400)', margin: 0 }}>
                    Se mostrará alerta cuando el stock de una variante caiga por debajo de este valor.
                  </p>
                </div>
              </div>

              {/* Vista previa */}
              <div className="section-card">
                <div className="section-card-header"><span className="section-card-title">Vista previa del tema</span></div>
                <div className="section-card-body">
                  <div style={{ background: settings.primary_color || '#1f7a5c', color: '#fff', borderRadius: 10, padding: '1.25rem', marginBottom: '0.75rem' }}>
                    <div style={{ fontWeight: 800, fontSize: '1.1rem' }}>{settings.commercial_name || 'Tienda'}</div>
                    <div style={{ fontSize: '0.8125rem', opacity: 0.8, marginTop: 2 }}>{settings.contact_email}</div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                    <div style={{ flex: 1, height: 32, borderRadius: 8, background: settings.primary_color }} title="Color primario" />
                    <div style={{ flex: 1, height: 32, borderRadius: 8, background: settings.secondary_color }} title="Color secundario" />
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: '#677067' }}>
                    <div><strong>Moneda:</strong> {settings.currency}</div>
                    <div><strong>Stock mínimo:</strong> {settings.stock_threshold} uds</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div style={{ marginTop: '1.5rem' }}>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar configuración'}
            </button>
          </div>
        </form>
      )}

      {/* ── Messages ── */}
      {tab === 'messages' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <span style={{ color: '#677067', fontSize: '0.875rem' }}>{messages.length} mensaje(s) configurados</span>
            <button className="btn btn-primary btn-sm" onClick={() => { setMessageForm(emptyMessage); setMsgModal(true); }}>
              <Plus size={15} /> Nuevo mensaje
            </button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>Título</th><th>Tipo</th><th>Estado</th><th>Vigencia</th><th style={{textAlign:'right'}}>Acciones</th></tr>
              </thead>
              <tbody>
                {messages.map((msg) => (
                  <tr key={msg.id}>
                    <td>
                      <strong style={{ display: 'block', fontSize: '0.875rem' }}>{msg.title}</strong>
                      <span style={{ fontSize: '0.78rem', color: '#9ca4a0' }}>{msg.content?.slice(0, 60)}…</span>
                    </td>
                    <td>
                      <Badge variant={msg.type === 'promo' ? 'accent' : msg.type === 'warning' ? 'warning' : 'info'}>
                        {msg.type}
                      </Badge>
                    </td>
                    <td><Badge variant={msg.active ? 'success' : 'neutral'}>{msg.active ? 'Activo' : 'Inactivo'}</Badge></td>
                    <td style={{ fontSize: '0.8125rem', color: '#9ca4a0' }}>
                      {msg.start_date ? `${msg.start_date} → ${msg.end_date || '∞'}` : 'Siempre'}
                    </td>
                    <td>
                      <div className="table-actions" style={{ justifyContent: 'flex-end' }}>
                        <button className="btn btn-danger btn-sm btn-icon" onClick={() => deleteMessage(msg.id)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {messages.length === 0 && <tr><td colSpan={5} className="state">Sin mensajes configurados</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal
        open={msgModal}
        onClose={() => setMsgModal(false)}
        title="Nuevo mensaje informativo"
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setMsgModal(false)}>Cancelar</button>
            <button className="btn btn-primary" form="msg-form" type="submit" disabled={saving}>Crear mensaje</button>
          </>
        }
      >
        <form id="msg-form" onSubmit={createMessage} style={{ display: 'grid', gap: '0.1rem' }}>
          <label>Título * <input value={messageForm.title} onChange={(e) => setMessageForm({ ...messageForm, title: e.target.value })} required /></label>
          <label>Contenido * <textarea value={messageForm.content} onChange={(e) => setMessageForm({ ...messageForm, content: e.target.value })} required /></label>
          <label>Tipo
            <select value={messageForm.type} onChange={(e) => setMessageForm({ ...messageForm, type: e.target.value })}>
              <option value="info">Informativo</option>
              <option value="promo">Promoción</option>
              <option value="warning">Alerta</option>
            </select>
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <label>Fecha inicio <input type="date" value={messageForm.start_date || ''} onChange={(e) => setMessageForm({ ...messageForm, start_date: e.target.value })} /></label>
            <label>Fecha fin <input type="date" value={messageForm.end_date || ''} onChange={(e) => setMessageForm({ ...messageForm, end_date: e.target.value })} /></label>
          </div>
          <label className="check-inline" style={{ marginTop: '0.5rem' }}>
            <input type="checkbox" checked={messageForm.active} onChange={(e) => setMessageForm({ ...messageForm, active: e.target.checked })} />
            Activo
          </label>
        </form>
      </Modal>
    </AdminLayout>
  );
}
