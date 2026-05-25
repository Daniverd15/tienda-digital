/**
 * Componente Badge: etiqueta de estado con color.
 *
 * Uso: <Badge variant="success">Aprobado</Badge>
 *
 * Props:
 *   - children: contenido textual de la etiqueta
 *   - variant: paleta de color a aplicar (mapeada a clases CSS .badge-*)
 *   - dot: si true, muestra un punto del color junto al texto (estilo
 *     "indicador de estado" como en Slack/Discord)
 *
 * Las variants disponibles estan definidas en global.css:
 *   success | error | warning | info | neutral | brand | accent
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

/**
 * Helper especifico para estados de pedido. Mapea el status (PAID, ENVIADO,
 * etc.) al variant y label correctos. Si el status es desconocido, muestra
 * el string raw como fallback.
 */
export function OrderStatusBadge({ status }) {
  const cfg = ORDER_STATUS[status] || { variant: 'neutral', label: status };
  return <Badge variant={cfg.variant} dot>{cfg.label}</Badge>;
}

/**
 * Helper especifico para estados de pago (APPROVED, REJECTED, etc.).
 */
export function PaymentStatusBadge({ status }) {
  const cfg = PAYMENT_STATUS[status] || { variant: 'neutral', label: status };
  return <Badge variant={cfg.variant} dot>{cfg.label}</Badge>;
}
