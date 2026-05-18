export const REVENUE_ORDER_STATUSES = new Set([
  'PAID',
  'EN_PREPARACION',
  'ENVIADO',
  'ENTREGADO',
  'entregado',
  'preparacion',
  'enviado',
]);

export const ORDER_STATUS_LABELS = {
  CREATED: 'Creado',
  AWAITING_PAYMENT: 'Esperando pago',
  PAID: 'Pagado',
  PAGO_PENDIENTE: 'Pago pendiente',
  PAGO_RECHAZADO: 'Pago rechazado',
  SIN_STOCK: 'Sin stock',
  EN_PREPARACION: 'En preparacion',
  ENVIADO: 'Enviado',
  ENTREGADO: 'Entregado',
  CANCELADA: 'Cancelada',
  EXPIRADA: 'Expirada',
  pendiente_pago: 'Pendiente pago',
  preparacion: 'En preparacion',
  enviado: 'Enviado',
  entregado: 'Entregado',
  cancelado: 'Cancelado',
  rechazado: 'Rechazado',
};

export const ORDER_STATUS_COLORS = {
  CREATED: '#64748b',
  AWAITING_PAYMENT: '#f59e0b',
  PAID: '#1f7a5c',
  PAGO_PENDIENTE: '#f59e0b',
  PAGO_RECHAZADO: '#ef4444',
  SIN_STOCK: '#991b1b',
  EN_PREPARACION: '#3b82f6',
  ENVIADO: '#8b5cf6',
  ENTREGADO: '#22c55e',
  CANCELADA: '#9ca3af',
  EXPIRADA: '#6b7280',
  pendiente_pago: '#f59e0b',
  preparacion: '#3b82f6',
  enviado: '#8b5cf6',
  entregado: '#22c55e',
  cancelado: '#9ca3af',
  rechazado: '#ef4444',
};

const numberValue = (value) => Number(value || 0);

export function orderStatusLabel(status) {
  return ORDER_STATUS_LABELS[status] || status || 'Sin estado';
}

export function buildOrderStatusData(orders = []) {
  const counts = orders.reduce((acc, order) => {
    const status = order.status || 'SIN_ESTADO';
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {});

  return Object.entries(counts)
    .map(([status, count]) => ({
      status,
      label: orderStatusLabel(status),
      count,
      fill: ORDER_STATUS_COLORS[status] || '#9ca3af',
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

export function buildTopProducts(orders = [], limit = 5) {
  const totals = {};

  orders
    .filter((order) => REVENUE_ORDER_STATUSES.has(order.status))
    .forEach((order) => {
      (order.items || []).forEach((item) => {
        const productName = item.product_name || 'Producto sin nombre';
        const key = item.product_id || productName;
        if (!totals[key]) {
          totals[key] = {
            product_id: item.product_id,
            product_name: productName,
            quantity: 0,
            revenue: 0,
          };
        }
        totals[key].quantity += numberValue(item.quantity);
        totals[key].revenue += numberValue(item.total);
      });
    });

  return Object.values(totals)
    .filter((item) => item.quantity > 0)
    .sort((a, b) => b.quantity - a.quantity || b.revenue - a.revenue)
    .slice(0, limit);
}

export function buildExpenseBreakdown(expenses = []) {
  const totals = expenses.reduce((acc, expense) => {
    const type = expense.expense_type || 'Otro';
    acc[type] = (acc[type] || 0) + numberValue(expense.amount);
    return acc;
  }, {});

  return Object.entries(totals)
    .map(([type, amount]) => ({ type, amount }))
    .filter((item) => item.amount > 0)
    .sort((a, b) => b.amount - a.amount);
}

export function buildFinanceInsights(dash, topProducts = [], expenseBreakdown = []) {
  const insights = [];
  const netProfit = numberValue(dash?.utilidad_neta);
  const grossSales = numberValue(dash?.ventas_brutas);
  const operatingCosts = numberValue(dash?.costos_operativos);
  const payroll = numberValue(dash?.nomina);

  if (netProfit < 0) {
    insights.push('La utilidad neta esta en negativo: los costos superan las ventas registradas.');
  } else if (grossSales > 0) {
    insights.push('La operacion tiene utilidad positiva sobre las ventas registradas.');
  } else {
    insights.push('Aun no hay ventas aprobadas para evaluar rentabilidad.');
  }

  if (topProducts[0]) {
    insights.push(`${topProducts[0].product_name} lidera las ventas con ${topProducts[0].quantity} unidades.`);
  }

  if (expenseBreakdown[0]) {
    insights.push(`${expenseBreakdown[0].type} es el mayor gasto operativo registrado.`);
  }

  if (payroll > grossSales && payroll > 0) {
    insights.push('La nomina activa supera las ventas brutas del periodo.');
  } else if (operatingCosts > grossSales && operatingCosts > 0) {
    insights.push('Los gastos operativos superan las ventas brutas del periodo.');
  }

  return insights;
}
