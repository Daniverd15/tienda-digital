import { useState } from 'react';
import { CheckCircle, Search, Star, XCircle } from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import AdminLayout from '../components/AdminLayout';
import Badge from '../components/Badge';
import { useToast } from '../context/ToastContext';

function StarRow({ rating }) {
  return (
    <div style={{ display: 'flex', gap: 2 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={13} fill={i <= rating ? '#ca8a04' : 'none'} color={i <= rating ? '#ca8a04' : '#c5ccbf'} />
      ))}
    </div>
  );
}

export default function AdminReviews() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [reviews, setReviews] = useState([]);

  const { loading, error } = useAsync(async () => {
    const { data } = await api.get('/admin/reviews');
    setReviews(data);
    return data;
  }, []);

  const updateApproval = async (review, approved) => {
    try {
      await api.patch(`/admin/reviews/${review.id}?approved=${approved}`);
      setReviews((prev) => prev.map((r) => (r.id === review.id ? { ...r, approved } : r)));
      toast(approved ? 'Reseña aprobada.' : 'Reseña rechazada.', 'success');
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al actualizar reseña.', 'error');
    }
  };

  if (loading) return <AdminLayout><div className="state">Cargando reseñas...</div></AdminLayout>;
  if (error)   return <AdminLayout><div className="state error">{error}</div></AdminLayout>;

  const filtered = reviews.filter((r) => {
    const matchFilter =
      filter === 'all' ||
      (filter === 'approved' && r.approved) ||
      (filter === 'pending' && !r.approved);
    const matchSearch =
      !search ||
      String(r.product_id).includes(search) ||
      (r.comment || '').toLowerCase().includes(search.toLowerCase());
    return matchFilter && matchSearch;
  });

  const counts = {
    all: reviews.length,
    approved: reviews.filter((r) => r.approved).length,
    pending: reviews.filter((r) => !r.approved).length,
  };

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">RF-09</span>
          <h1 className="page-title">Gestión de reseñas</h1>
        </div>
        <div className="page-actions">
          <span style={{ fontSize: '0.875rem', color: '#677067' }}>{reviews.length} reseñas totales</span>
        </div>
      </div>

      {/* Filter chips */}
      <div className="filter-row" style={{ marginBottom: '1rem' }}>
        {[
          { id: 'all',      label: 'Todas' },
          { id: 'approved', label: 'Aprobadas' },
          { id: 'pending',  label: 'Pendientes' },
        ].map((f) => (
          <button
            key={f.id}
            className={`filter-chip${filter === f.id ? ' active' : ''}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
            {counts[f.id] > 0 && (
              <span style={{
                background: filter === f.id ? 'rgba(255,255,255,0.3)' : 'var(--neutral-200)',
                color: filter === f.id ? '#fff' : 'var(--neutral-600)',
                borderRadius: 99, fontSize: '0.7rem', padding: '0px 6px', fontWeight: 800,
              }}>
                {counts[f.id]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="admin-search-bar" style={{ marginBottom: '1.25rem' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 360 }}>
          <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#9ca4a0' }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por comentario o producto…"
            style={{ paddingLeft: 36 }}
          />
        </div>
        <span style={{ fontSize: '0.8125rem', color: '#9ca4a0' }}>{filtered.length} resultado(s)</span>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Producto</th>
              <th>Pedido</th>
              <th>Calificación</th>
              <th>Comentario</th>
              <th>Estado</th>
              <th style={{ textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={7} className="state">Sin reseñas con ese filtro</td></tr>
            ) : (
              filtered.map((r) => (
                <tr key={r.id}>
                  <td style={{ color: 'var(--neutral-400)', fontSize: '0.8125rem' }}>#{r.id}</td>
                  <td>
                    <span className="category-chip">Prod. #{r.product_id}</span>
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--neutral-500)' }}>#{r.order_id}</td>
                  <td>
                    <StarRow rating={r.rating} />
                    <span style={{ fontSize: '0.75rem', color: 'var(--neutral-400)', marginTop: 2 }}>
                      {r.rating}/5
                    </span>
                  </td>
                  <td style={{ maxWidth: 260, color: 'var(--neutral-700)', fontSize: '0.875rem' }}>
                    {r.comment
                      ? <span title={r.comment}>{r.comment.length > 80 ? r.comment.slice(0, 80) + '…' : r.comment}</span>
                      : <span style={{ color: 'var(--neutral-400)', fontStyle: 'italic' }}>Sin comentario</span>
                    }
                  </td>
                  <td>
                    <Badge variant={r.approved ? 'success' : 'warning'}>
                      {r.approved ? 'Aprobada' : 'Pendiente'}
                    </Badge>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div className="table-actions" style={{ justifyContent: 'flex-end' }}>
                      {r.approved ? (
                        <button
                          className="btn btn-danger btn-sm btn-icon"
                          onClick={() => updateApproval(r, false)}
                          title="Rechazar reseña"
                        >
                          <XCircle size={14} />
                        </button>
                      ) : (
                        <button
                          className="btn btn-secondary btn-sm btn-icon"
                          onClick={() => updateApproval(r, true)}
                          title="Aprobar reseña"
                          style={{ color: 'var(--success-text)', borderColor: 'var(--success-border)' }}
                        >
                          <CheckCircle size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Summary cards */}
      <div className="metric-grid" style={{ marginTop: '1.5rem' }}>
        {[
          ['Total reseñas', reviews.length],
          ['Aprobadas', counts.approved],
          ['Pendientes', counts.pending],
          ['Promedio ★', reviews.length ? (reviews.reduce((s, r) => s + r.rating, 0) / reviews.length).toFixed(1) : '—'],
        ].map(([label, value]) => (
          <div key={label} className="metric-card">
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
    </AdminLayout>
  );
}
