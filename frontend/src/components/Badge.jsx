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

/* ── Status helpers ──
 * Cubre los valores que devuelven los microservicios (mayusculas) y los del
 * monolito legacy (minusculas), para que la UI funcione con ambos.
 */
const ORDER_STATUS = {
  // microservicios
  CREATED:         { variant: 'neutral', label: 'Creado' },
  AWAITING_PAYMENT:{ variant: 'warning', label: 'Esperando pago' },
  PAID:            { variant: 'brand',   label: 'Pagado' },
  PAGO_PENDIENTE:  { variant: 'warning', label: 'Pago pendiente' },
  PAGO_RECHAZADO:  { variant: 'error',   label: 'Pago rechazado' },
  SIN_STOCK:       { variant: 'error',   label: 'Sin stock' },
  EN_PREPARACION:  { variant: 'info',    label: 'En preparación' },
  ENVIADO:         { variant: 'brand',   label: 'Enviado' },
  ENTREGADO:       { variant: 'success', label: 'Entregado' },
  CANCELADA:       { variant: 'error',   label: 'Cancelada' },
  EXPIRADA:        { variant: 'error',   label: 'Expirada' },
  // monolito legacy
  pendiente_pago:  { variant: 'warning', label: 'Pendiente pago' },
  preparacion:     { variant: 'info',    label: 'En preparación' },
  enviado:         { variant: 'brand',   label: 'Enviado' },
  entregado:       { variant: 'success', label: 'Entregado' },
  cancelado:       { variant: 'error',   label: 'Cancelado' },
  rechazado:       { variant: 'error',   label: 'Rechazado' },
};

const PAYMENT_STATUS = {
  // microservicios
  APPROVED:  { variant: 'success', label: 'Aprobado' },
  REJECTED:  { variant: 'error',   label: 'Rechazado' },
  PENDING:   { variant: 'warning', label: 'Pendiente' },
  FAILED:    { variant: 'error',   label: 'Fallido' },
  // monolito legacy
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
