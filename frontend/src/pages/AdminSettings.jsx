import { useEffect, useState } from 'react';
import { Megaphone, Settings, Trash2, Plus } from 'lucide-react';
import api from '../api/client';
import AdminLayout from '../components/AdminLayout';
import Badge from '../components/Badge';
import Modal from '../components/Modal';
import { useToast } from '../context/ToastContext';

const emptyMessage = { title: '', content: '', type: 'info', active: true, start_date: '', end_date: '' };

const SETTINGS_LABELS = {
  commercial_name: 'Nombre comercial',
  contact_email:   'Email de contacto',
  contact_phone:   'Teléfono de contacto',
  currency:        'Moneda',
  logo_url:        'URL del logo',
  banner_url:      'URL del banner',
  primary_color:   'Color primario',
  secondary_color: 'Color secundario',
  stock_threshold: 'Umbral de stock mínimo',
};

const TABS = [
  { id: 'store',    label: 'Tienda',             icon: <Settings size={15} /> },
  { id: 'messages', label: 'Mensajes informativos', icon: <Megaphone size={15} /> },
];

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
      toast('Configuración guardada.', 'success');
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

  const skipFields = ['id', 'created_at', 'updated_at'];

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

      {/* Store settings */}
      {tab === 'store' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: '1.5rem', alignItems: 'start' }}>
          <form onSubmit={saveSettings}>
            <div className="section-card">
              <div className="section-card-header">
                <span className="section-card-title">Datos generales de la tienda</span>
              </div>
              <div className="section-card-body" style={{ display: 'grid', gap: '0.1rem' }}>
                {Object.keys(settings).filter((k) => !skipFields.includes(k)).map((field) => (
                  <label key={field}>
                    {SETTINGS_LABELS[field] || field.replace(/_/g, ' ')}
                    <input
                      type={field === 'stock_threshold' ? 'number' : field.includes('color') ? 'color' : 'text'}
                      value={settings[field] ?? ''}
                      onChange={(e) => setSettings({
                        ...settings,
                        [field]: field === 'stock_threshold' ? Number(e.target.value) : e.target.value,
                      })}
                      required={!['logo_url', 'banner_url'].includes(field)}
                    />
                  </label>
                ))}
                <button type="submit" className="btn btn-primary" style={{ marginTop: '1rem' }} disabled={saving}>
                  {saving ? 'Guardando...' : 'Guardar configuración'}
                </button>
              </div>
            </div>
          </form>

          {/* Preview panel */}
          <div>
            <div className="section-card">
              <div className="section-card-header"><span className="section-card-title">Vista previa</span></div>
              <div className="section-card-body">
                <div style={{
                  background: settings.primary_color || '#1f7a5c',
                  color: '#fff',
                  borderRadius: 12,
                  padding: '1.5rem',
                  marginBottom: '1rem',
                }}>
                  <div style={{ fontWeight: 800, fontSize: '1.25rem' }}>{settings.commercial_name || 'Tienda'}</div>
                  <div style={{ fontSize: '0.875rem', opacity: 0.8, marginTop: 4 }}>{settings.contact_email}</div>
                </div>
                <div style={{ fontSize: '0.8125rem', color: '#677067', display: 'grid', gap: '0.4rem' }}>
                  <div><strong>Moneda:</strong> {settings.currency}</div>
                  <div><strong>Stock mínimo:</strong> {settings.stock_threshold} unidades</div>
                  <div><strong>Teléfono:</strong> {settings.contact_phone}</div>
                </div>
              </div>
            </div>

            {settings.logo_url && (
              <div className="section-card" style={{ marginTop: '1rem' }}>
                <div className="section-card-header"><span className="section-card-title">Logo actual</span></div>
                <div className="section-card-body">
                  <img src={settings.logo_url} alt="Logo" style={{ maxWidth: '100%', maxHeight: 80, objectFit: 'contain' }} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Messages */}
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

      {/* Create message modal */}
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
