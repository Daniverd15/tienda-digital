import { useEffect, useState } from 'react';
import api from '../api/client';

const emptyMessage = { title: '', content: '', type: 'info', active: true, start_date: '', end_date: '' };

export default function AdminSettings() {
  const [settings, setSettings] = useState(null);
  const [messages, setMessages] = useState([]);
  const [audits, setAudits] = useState([]);
  const [messageForm, setMessageForm] = useState(emptyMessage);

  const load = async () => {
    const [settingsRes, messagesRes, auditsRes] = await Promise.all([
      api.get('/admin/settings'),
      api.get('/admin/messages'),
      api.get('/admin/audit-logs')
    ]);
    setSettings(settingsRes.data);
    setMessages(messagesRes.data);
    setAudits(auditsRes.data);
  };

  useEffect(() => {
    load();
  }, []);

  const saveSettings = async (event) => {
    event.preventDefault();
    const { data } = await api.put('/admin/settings', settings);
    setSettings(data);
    load();
  };

  const createMessage = async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(Object.entries(messageForm).map(([key, value]) => [key, value === '' ? null : value]));
    await api.post('/admin/messages', payload);
    setMessageForm(emptyMessage);
    load();
  };

  if (!settings) return <div className="state">Cargando configuracion...</div>;

  return (
    <main className="page-shell admin-grid-page">
      <span className="eyebrow">RF-09</span>
      <h1>Configuracion, mensajes y auditoria</h1>
      <section className="admin-section">
        <form onSubmit={saveSettings}>
          <h2>Tienda</h2>
          {Object.keys(settings).filter((field) => field !== 'id').map((field) => (
            <input
              key={field}
              placeholder={field}
              value={settings[field] ?? ''}
              onChange={(event) => setSettings({ ...settings, [field]: field === 'stock_threshold' ? Number(event.target.value) : event.target.value })}
              required={!['logo_url', 'banner_url'].includes(field)}
            />
          ))}
          <button className="primary-button">Guardar configuracion</button>
        </form>
        <form onSubmit={createMessage}>
          <h2>Mensaje informativo</h2>
          <input placeholder="Titulo" value={messageForm.title} onChange={(event) => setMessageForm({ ...messageForm, title: event.target.value })} required />
          <textarea placeholder="Contenido" value={messageForm.content} onChange={(event) => setMessageForm({ ...messageForm, content: event.target.value })} required />
          <select value={messageForm.type} onChange={(event) => setMessageForm({ ...messageForm, type: event.target.value })}>
            <option value="info">Info</option>
            <option value="promo">Promo</option>
            <option value="warning">Alerta</option>
          </select>
          <input type="date" value={messageForm.start_date || ''} onChange={(event) => setMessageForm({ ...messageForm, start_date: event.target.value })} />
          <input type="date" value={messageForm.end_date || ''} onChange={(event) => setMessageForm({ ...messageForm, end_date: event.target.value })} />
          <button className="primary-button">Crear mensaje</button>
        </form>
      </section>
      <section className="admin-section">
        <div className="table-list">
          <h2>Mensajes</h2>
          {messages.map((message) => (
            <article className="row-card" key={message.id}>
              <strong>{message.title}</strong>
              <span>{message.type}</span>
              <span>{message.active ? 'Activo' : 'Inactivo'}</span>
              <span>{message.content}</span>
            </article>
          ))}
        </div>
        <div className="table-list">
          <h2>Bitacora</h2>
          {audits.map((audit) => (
            <article className="row-card" key={audit.id}>
              <strong>{audit.action}</strong>
              <span>{audit.entity}</span>
              <span>{audit.entity_id}</span>
              <span>{audit.created_at}</span>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

