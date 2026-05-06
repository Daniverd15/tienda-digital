import { Link, useParams } from 'react-router-dom';
import {
  CheckCircle,
  Circle,
  Package,
  Star,
  Truck,
} from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { OrderStatusBadge, PaymentStatusBadge } from '../components/Badge';

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;

const ORDER_STEPS = [
  { key: 'pendiente_pago', label: 'Pendiente de pago' },
  { key: 'preparacion',    label: 'En preparación' },
  { key: 'enviado',        label: 'Enviado' },
  { key: 'entregado',      label: 'Entregado' },
];

function OrderTimeline({ status }) {
  const stepIndex = ORDER_STEPS.findIndex((s) => s.key === status);

  return (
    <div className="order-timeline">
      {ORDER_STEPS.map((step, i) => {
        const done   = i < stepIndex || (status === 'entregado' && i <= stepIndex);
        const active = i === stepIndex && status !== 'cancelado' && status !== 'rechazado';
        return (
          <div key={step.key} className="timeline-step">
            <div className={`timeline-dot ${done ? 'done' : active ? 'active' : ''}`}>
              {done ? <CheckCircle size={12} color="#fff" /> : active ? <Circle size={10} color="#fff" fill="#fff" /> : null}
            </div>
            <div className="timeline-content">
              <strong style={{ color: done || active ? 'var(--neutral-900)' : 'var(--neutral-400)' }}>
                {step.label}
              </strong>
              {active && <span>Estado actual del pedido</span>}
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

  if (loading) return <div className="state">Cargando pedido...</div>;
  if (error)   return <div className="state error">{error}</div>;

  const canReview = order.status === 'entregado' && order.payment_status === 'aprobado';

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

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: '1.5rem', alignItems: 'start' }}>
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
                  {order.items.map((item) => (
                    <tr key={item.id}>
                      <td><strong>{item.product_name}</strong></td>
                      <td style={{ color: 'var(--neutral-500)', fontSize: '0.8125rem' }}>{item.variant_description || '—'}</td>
                      <td>{item.quantity}</td>
                      <td style={{ textAlign: 'right', fontWeight: 800 }}>{COP(item.total)}</td>
                      {canReview && (
                        <td>
                          <Link
                            to={`/resenas/${order.id}/${item.product_id}`}
                            className="btn btn-ghost btn-sm"
                            style={{ gap: 4 }}
                          >
                            <Star size={13} /> Reseñar
                          </Link>
                        </td>
                      )}
                    </tr>
                  ))}
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
          {!['cancelado','rechazado'].includes(order.status) && (
            <div className="section-card">
              <div className="section-card-header"><span className="section-card-title">Progreso del pedido</span></div>
              <div className="section-card-body">
                <OrderTimeline status={order.status} />
              </div>
            </div>
          )}

          {order.status === 'cancelado' && (
            <div className="alert error">Este pedido fue cancelado.</div>
          )}
          {order.status === 'rechazado' && (
            <div className="alert error">El pago de este pedido fue rechazado.</div>
          )}

          {canReview && (
            <div className="alert success">
              ¡Pedido entregado! Puedes dejar reseñas en los productos de este pedido.
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
