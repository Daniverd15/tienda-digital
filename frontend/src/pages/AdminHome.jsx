import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Legend,
} from 'recharts';
import {
  AlertTriangle,
  ArrowRight,
  BarChart2,
  DollarSign,
  Package,
  ShoppingCart,
  TrendingUp,
  Users,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import AdminLayout from '../components/AdminLayout';
import { OrderStatusBadge, PaymentStatusBadge } from '../components/Badge';

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;

const STATUS_COLORS = {
  pendiente_pago: '#f59e0b',
  preparacion:    '#3b82f6',
  enviado:        '#8b5cf6',
  entregado:      '#22c55e',
  rechazado:      '#ef4444',
  cancelado:      '#9ca3af',
};

function KpiCard({ icon, label, value, sub, color }) {
  return (
    <div className={`kpi-card kpi-${color}`}>
      <div className="kpi-icon">{icon}</div>
      <div className="kpi-body">
        <div className="kpi-label">{label}</div>
        <div className="kpi-value">{value}</div>
        {sub && <div className="kpi-sub">{sub}</div>}
      </div>
    </div>
  );
}

const CustomBarTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#fff', border: '1px solid #e1e5de', borderRadius: 8, padding: '0.65rem 1rem', fontSize: '0.8125rem', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
      <strong style={{ display: 'block', marginBottom: 4, color: '#172026' }}>{payload[0].payload.product_name}</strong>
      <span style={{ color: '#4c5960' }}>Vendidos: <strong style={{ color: '#1f7a5c' }}>{payload[0].value}</strong></span>
    </div>
  );
};

const CustomPieTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#fff', border: '1px solid #e1e5de', borderRadius: 8, padding: '0.6rem 0.9rem', fontSize: '0.8125rem', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
      <strong>{payload[0].name}</strong>: {payload[0].value}
    </div>
  );
};

export default function AdminHome() {
  const { data, loading, error } = useAsync(async () => {
    const [dash, orders, alerts, customers] = await Promise.all([
      api.get('/admin/dashboard'),
      api.get('/admin/orders'),
      api.get('/admin/inventory/alerts'),
      api.get('/admin/customers'),
    ]);
    return {
      dash: dash.data,
      orders: orders.data,
      alerts: alerts.data,
      customerCount: customers.data.length,
    };
  }, []);

  if (loading) {
    return (
      <AdminLayout>
        <div className="page-header">
          <div className="page-header-left">
            <span className="page-eyebrow">Operación</span>
            <h1 className="page-title">Dashboard</h1>
          </div>
        </div>
        <div className="kpi-grid">
          {[0,1,2,3].map((i) => (
            <div key={i} className="kpi-card" style={{ height: 96 }}>
              <div className="skeleton" style={{ width: '100%', height: '100%', borderRadius: 12 }} />
            </div>
          ))}
        </div>
        <div className="state">Cargando dashboard...</div>
      </AdminLayout>
    );
  }

  if (error) {
    return (
      <AdminLayout>
        <div className="state error">Error al cargar el dashboard: {error}</div>
      </AdminLayout>
    );
  }

  const { dash, orders, alerts, customerCount } = data;
  const recentOrders = [...orders].reverse().slice(0, 6);
  const pieData = (dash.pedidos_por_estado || []).filter((d) => d.count > 0);
  const barData = dash.productos_mas_vendidos || [];

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">Operación</span>
          <h1 className="page-title">Dashboard</h1>
        </div>
        <div className="page-actions">
          <Link to="/admin/finanzas" className="btn btn-secondary btn-sm">
            <BarChart2 size={15} /> Ver finanzas
          </Link>
        </div>
      </div>

      {/* KPI cards */}
      <div className="kpi-grid">
        <KpiCard
          icon={<DollarSign size={22} />}
          label="Ventas brutas"
          value={COP(dash.ventas_brutas)}
          sub={`${dash.ordenes_aprobadas || 0} pedidos aprobados`}
          color="green"
        />
        <KpiCard
          icon={<ShoppingCart size={22} />}
          label="Pedidos totales"
          value={orders.length}
          sub="Todos los estados"
          color="blue"
        />
        <KpiCard
          icon={<Users size={22} />}
          label="Clientes registrados"
          value={customerCount}
          sub="Cuentas activas"
          color="purple"
        />
        <KpiCard
          icon={<TrendingUp size={22} />}
          label="Utilidad neta"
          value={COP(dash.utilidad_neta)}
          sub={`COGS + Op + Nómina descontados`}
          color={dash.utilidad_neta >= 0 ? 'green' : 'orange'}
        />
      </div>

      {/* Charts */}
      <div className="charts-grid">
        {/* Bar chart — top products */}
        <div className="chart-card">
          <div className="chart-title">
            Productos más vendidos
            <span style={{ fontSize: '0.8rem', color: '#9ca4a0', fontWeight: 400 }}>
              Por unidades
            </span>
          </div>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={barData} barCategoryGap="35%">
                <XAxis
                  dataKey="product_name"
                  tick={{ fontSize: 12, fill: '#4c5960' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: '#9ca4a0' }}
                  axisLine={false}
                  tickLine={false}
                  width={28}
                />
                <Tooltip content={<CustomBarTooltip />} cursor={{ fill: 'rgba(31,122,92,0.06)' }} />
                <Bar dataKey="quantity" radius={[6,6,0,0]}>
                  {barData.map((entry, i) => (
                    <Cell key={i} fill={i === 0 ? '#1f7a5c' : i === 1 ? '#30a87e' : '#54c59c'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="state" style={{ height: 220, padding: 0 }}>Sin ventas registradas aún</div>
          )}
        </div>

        {/* Pie chart — orders by status */}
        <div className="chart-card">
          <div className="chart-title">Pedidos por estado</div>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="count"
                  nameKey="status"
                  cx="50%"
                  cy="45%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={3}
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={STATUS_COLORS[entry.status] || '#9ca3af'} />
                  ))}
                </Pie>
                <Tooltip content={<CustomPieTooltip />} />
                <Legend
                  formatter={(value) => (
                    <span style={{ fontSize: '0.78rem', color: '#4c5960' }}>{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="state" style={{ height: 220, padding: 0 }}>Sin pedidos registrados</div>
          )}
        </div>
      </div>

      {/* Finance summary row */}
      <div className="metric-grid" style={{ marginBottom: '1.5rem' }}>
        {[
          ['COGS',              COP(dash.cogs)],
          ['Costos operativos', COP(dash.costos_operativos)],
          ['Nómina',            COP(dash.nomina)],
          ['Rotación inventario', `${dash.rotacion_inventario ?? 0} ×`],
        ].map(([label, value]) => (
          <div key={label} className="metric-card">
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      {/* Bottom grid */}
      <div className="dash-bottom">
        {/* Recent orders */}
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">Pedidos recientes</span>
            <Link to="/admin/pedidos" className="btn btn-ghost btn-sm">
              Ver todos <ArrowRight size={14} />
            </Link>
          </div>
          <div className="table-wrap" style={{ border: 'none', borderRadius: 0, boxShadow: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Estado</th>
                  <th>Pago</th>
                  <th style={{ textAlign: 'right' }}>Total</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.length === 0 ? (
                  <tr><td colSpan={4} style={{ textAlign: 'center', color: '#9ca4a0', padding: '2rem' }}>Sin pedidos</td></tr>
                ) : (
                  recentOrders.map((order) => (
                    <tr key={order.id}>
                      <td><span className="font-mono" style={{ fontWeight: 700, fontSize: '0.8125rem' }}>{order.order_code}</span></td>
                      <td><OrderStatusBadge status={order.status} /></td>
                      <td><PaymentStatusBadge status={order.payment_status} /></td>
                      <td style={{ textAlign: 'right', fontWeight: 700 }}>{COP(order.total)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Stock alerts */}
        <div className="section-card">
          <div className="section-card-header">
            <span className="section-card-title">
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertTriangle size={15} color="#ca8a04" />
                Alertas de stock
              </span>
            </span>
            <Link to="/admin/catalogo" className="btn btn-ghost btn-sm">
              Inventario <ArrowRight size={14} />
            </Link>
          </div>
          <div className="section-card-body" style={{ padding: '0.75rem' }}>
            {alerts.length === 0 ? (
              <div className="state" style={{ padding: '2rem', fontSize: '0.875rem' }}>
                Sin alertas de stock mínimo
              </div>
            ) : (
              alerts.map((a) => (
                <div
                  key={a.variant_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.7rem 0.75rem',
                    borderRadius: 8,
                    background: a.stock === 0 ? 'var(--error-bg)' : 'var(--warning-bg)',
                    marginBottom: '0.5rem',
                    gap: '0.75rem',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#172026' }}>{a.product_name}</div>
                    <div style={{ fontSize: '0.75rem', color: '#677067' }}>SKU: {a.sku}</div>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{ fontSize: '1rem', fontWeight: 800, color: a.stock === 0 ? '#991b1b' : '#854d0e' }}>
                      {a.stock} uds
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#9ca4a0' }}>mín {a.threshold}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
