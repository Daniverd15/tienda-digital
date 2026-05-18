import api from '../api/client';
import { useAsync } from '../hooks/useAsync';

export default function Notifications() {
  const { data: notifications, loading, error, setData } = useAsync(async () => {
    const { data } = await api.get('/notifications');
    return data;
  }, []);

  const markRead = async (notification) => {
    await api.patch(`/notifications/${notification.id}/read`);
    // En microservicios el campo es read_at (timestamp), no read (bool). Marcamos ambos.
    setData(notifications.map((item) =>
      item.id === notification.id ? { ...item, read: true, read_at: new Date().toISOString() } : item
    ));
  };

  if (loading) return <div className="state">Cargando notificaciones...</div>;
  if (error) return <div className="state error">{error}</div>;

  return (
    <main className="page-shell">
      <span className="eyebrow">Seguimiento</span>
      <h1>Notificaciones</h1>
      <div className="table-list">
        {notifications.map((notification) => (
          <article className={(notification.read || notification.read_at) ? 'row-card muted' : 'row-card'} key={notification.id}>
            <strong>{notification.title}</strong>
            <span>{notification.message}</span>
            <button className="ghost-button" onClick={() => markRead(notification)} disabled={(notification.read || notification.read_at)}>
              {(notification.read || notification.read_at) ? 'Leida' : 'Marcar leida'}
            </button>
          </article>
        ))}
      </div>
    </main>
  );
}

