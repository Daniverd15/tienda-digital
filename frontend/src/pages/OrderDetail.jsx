import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  CheckCircle,
  Circle,
  Package,
  Star,
  Truck,
  CreditCard,
  PackageCheck,
  Home,
} from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { OrderStatusBadge, PaymentStatusBadge } from '../components/Badge';

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;

/**
 * Los estados visibles para el cliente. Cubre tanto los nombres del monolito
 * legacy (pendiente_pago, preparacion...) como los de microservicios
 * (PAID, EN_PREPARACION, ENVIADO, ENTREGADO).
 */
const ORDER_STEPS = [
  { keys: ['PAID', 'pagado', 'pendiente_pago'],            label: 'Pago confirmado',  icon: CreditCard },
  { keys: ['EN_PREPARACION', 'preparacion'],               label: 'En preparación',   icon: PackageCheck },
  { keys: ['ENVIADO', 'enviado'],                          label: 'Enviado',          icon: Truck },
  { keys: ['ENTREGADO', 'entregado'],                      label: 'Entregado',        icon: Home },
];

function statusIndex(status) {
  for (let i = 0; i < ORDER_STEPS.length; i += 1) {
    if (ORDER_STEPS[i].keys.includes(status)) return i;
  }
  return -1;
}

function fmtDate(d) {
  if (!d) return '';
  try { return new Date(d).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }); }
  catch { return ''; }
}

function OrderTimeline({ order }) {
  const stepIndex = statusIndex(order.status);
  // Construimos un mapa de fecha por estado, usando order.history si viene.
  const dateByStep = {};
  (order.history || []).forEach((h) => {
    const idx = statusIndex(h.to_status);
    if (idx >= 0 && !dateByStep[idx]) dateByStep[idx] = h.changed_at;
  });
  // Si no hay history, al menos marcamos el primer paso con created_at
  if (stepIndex >= 0 && !dateByStep[0]) dateByStep[0] = order.created_at;

  return (
    <div className="order-timeline">
      {ORDER_STEPS.map((step, i) => {
        const Icon = step.icon;
        const done   = i < stepIndex;
        const active = i === stepIndex;
        const passed = done || active;
        const date = dateByStep[i];
        return (
          <div key={step.label} className="timeline-step">
            <div className={`timeline-dot ${done ? 'done' : active ? 'active' : ''}`}>
              {passed
                ? <Icon size={12} color="#fff" />
                : <Circle size={9} color="#cbd0c8" />}
            </div>
            <div className="timeline-content">
              <strong style={{ color: passed ? 'var(--neutral-900)' : 'var(--neutral-400)' }}>
                {step.label}
              </strong>
              {active && <span style={{ color: 'var(--brand-600)' }}>Estado actual</span>}
              {done && date && <span>{fmtDate(date)}</span>}
              {active && date && <span>{fmtDate(date)}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function OrderDetail() {
  const { id } = useParams();
  const { data: order, loading, error } = useAsync(async () => {
    const { data } = await api.get(`/orders/${id}`);
    return data;
  }, [id]);

  const [myReviews, setMyReviews] = useState([]);

  useEffect(() => {
    let active = true;
    api.get('/reviews/mine')
      .then(({ data }) => { if (active) setMyReviews(data || []); })
      .catch(() => { /* sin reviews aun */ });
    return () => { active = false; };
  }, []);

  if (loading) return <div className="state">Cargando pedido...</div>;
  if (error)   return <div className="state error">{error}</div>;

  const isDelivered = ['ENTREGADO', 'entregado'].includes(order.status);
  const isCancelled = ['CANCELADA', 'cancelado', 'EXPIRADA'].includes(order.status);
  const canReview = isDelivered;
  const reviewedProductIds = new Set(
    myReviews.filter((r) => r.order_id === order.id).map((r) => r.product_id),
  );

  return (
    <main className="page-shell">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
        <Link to="/mis-pedidos" style={{ color: 'var(--neutral-500)', fontSize: '0.875rem', textDecoration: 'none' }}>← Mis pedidos</Link>
      </div>
      <div className="section-heading">
        <div>
          <span className="eyebrow">Pedido</span>
          <h1 className="font-mono">{order.order_code}</h1>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <OrderStatusBadge status={order.status} />
          <PaymentStatusBadge status={order.payment_status} />
        </div>
      </div>

      <div className="order-detail-grid">
        {/* Left */}
        <div style={{ display: 'grid', gap: '1.25rem' }}>
          {/* Items */}
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title"><Package size={15} style={{ display:'inline',marginRight:6 }} />Artículos del pedido</span>
            </div>
            <div className="section-card-body" style={{ padding: 0 }}>
              <table className="data-table">
                <thead>
                  <tr><th>Producto</th><th>Variante</th><th>Cant.</th><th style={{textAlign:'right'}}>Total</th>{canReview && <th>Reseña</th>}</tr>
                </thead>
                <tbody>
                  {order.items.map((item) => {
                    const alreadyReviewed = reviewedProductIds.has(item.product_id);
                    return (
                      <tr key={item.id}>
                        <td><strong>{item.product_name}</strong></td>
                        <td style={{ color: 'var(--neutral-500)', fontSize: '0.8125rem' }}>{item.variant_description || '—'}</td>
                        <td>{item.quantity}</td>
                        <td style={{ textAlign: 'right', fontWeight: 800 }}>{COP(item.total)}</td>
                        {canReview && (
                          <td>
                            {alreadyReviewed ? (
                              <span className="badge badge-success">
                                <CheckCircle size={12} /> Reseñado
                              </span>
                            ) : (
                              <Link
                                to={`/resenas/${order.id}/${item.product_id}`}
                                className="btn btn-primary btn-sm"
                                style={{ gap: 4 }}
                              >
                                <Star size={13} /> Dejar reseña
                              </Link>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Delivery info */}
          <div className="section-card">
            <div className="section-card-header">
              <span className="section-card-title"><Truck size={15} style={{ display:'inline',marginRight:6 }} />Datos de entrega</span>
            </div>
            <div className="section-card-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.875rem' }}>
              <div><span style={{ color: 'var(--neutral-500)', fontSize: '0.75rem', fontWeight: 700, display:'block' }}>NOMBRE</span>{order.delivery_name}</div>
              <div><span style={{ color: 'var(--neutral-500)', fontSize: '0.75rem', fontWeight: 700, display:'block' }}>CIUDAD</span>{order.delivery_city}</div>
              <div><span style={{ color: 'var(--neutral-500)', fontSize: '0.75rem', fontWeight: 700, display:'block' }}>DIRECCIÓN</span>{order.delivery_address}</div>
              <div><span style={{ color: 'var(--neutral-500)', fontSize: '0.75rem', fontWeight: 700, display:'block' }}>TELÉFONO</span>{order.contact_phone}</div>
              <div><span style={{ color: 'var(--neutral-500)', fontSize: '0.75rem', fontWeight: 700, display:'block' }}>EMAIL</span>{order.contact_email}</div>
              <div><span style={{ color: 'var(--neutral-500)', fontSize: '0.75rem', fontWeight: 700, display:'block' }}>DOC. FACTURACIÓN</span>{order.billing_document}</div>
            </div>
          </div>
        </div>

        {/* Right */}
        <div style={{ display: 'grid', gap: '1rem' }}>
          {/* Summary */}
          <div className="cart-summary" style={{ position: 'static' }}>
            <h2 style={{ marginBottom: '1rem' }}>Resumen del pago</h2>
            <div className="summary-row">
              <span>Subtotal</span><span>{COP(order.subtotal)}</span>
            </div>
            <div className="summary-row">
              <span>Adicionales</span><span>{COP(order.additional_costs)}</span>
            </div>
            <div className="summary-row">
              <span>Descuento</span><span style={{ color: 'var(--brand-600)' }}>-{COP(order.discount)}</span>
            </div>
            <div className="summary-row total">
              <span>Total</span><span>{COP(order.total)}</span>
            </div>
          </div>

          {/* Timeline */}
          {!isCancelled && (
            <div className="section-card">
              <div className="section-card-header"><span className="section-card-title">Progreso del pedido</span></div>
              <div className="section-card-body">
                <OrderTimeline order={order} />
              </div>
            </div>
          )}

          {isCancelled && (
            <div className="alert error">Este pedido fue cancelado.</div>
          )}

          {canReview && (
            <div className="alert success">
              <Star size={16} />
              ¡Pedido entregado! Puedes dejar reseñas en los productos comprados.
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
