/**
 * Badge — color-coded status label.
 * variant: 'success' | 'error' | 'warning' | 'info' | 'neutral' | 'brand' | 'accent'
 */
export default function Badge({ children, variant = 'neutral', dot = false }) {
  return (
    <span className={`badge badge-${variant}`}>
      {dot && (
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'currentColor',
            flexShrink: 0,
          }}
        />
      )}
      {children}
    </span>
  );
}

/* ── Status helpers ── */
const ORDER_STATUS = {
  pendiente_pago: { variant: 'warning', label: 'Pendiente pago' },
  preparacion:    { variant: 'info',    label: 'En preparación' },
  enviado:        { variant: 'brand',   label: 'Enviado' },
  entregado:      { variant: 'success', label: 'Entregado' },
  cancelado:      { variant: 'error',   label: 'Cancelado' },
  rechazado:      { variant: 'error',   label: 'Rechazado' },
};

const PAYMENT_STATUS = {
  aprobado:  { variant: 'success', label: 'Aprobado' },
  rechazado: { variant: 'error',   label: 'Rechazado' },
  pendiente: { variant: 'warning', label: 'Pendiente' },
};

export function OrderStatusBadge({ status }) {
  const cfg = ORDER_STATUS[status] || { variant: 'neutral', label: status };
  return <Badge variant={cfg.variant} dot>{cfg.label}</Badge>;
}

export function PaymentStatusBadge({ status }) {
  const cfg = PAYMENT_STATUS[status] || { variant: 'neutral', label: status };
  return <Badge variant={cfg.variant} dot>{cfg.label}</Badge>;
}
