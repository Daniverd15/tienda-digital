/**
 * Pagina de Finanzas del admin (/admin/finanzas).
 *
 * ============================================================================
 * 3 TABS
 * ============================================================================
 *   - Dashboard: KPIs financieros + graficos (lineas, torta, barras) + tablas
 *   - Empleados: CRUD de empleados (afecta calculo de nomina)
 *   - Gastos:    CRUD de gastos operativos (afecta utilidad neta)
 *
 * ============================================================================
 * CALCULOS FINANCIEROS
 * ============================================================================
 * Se consultan a GET /admin/finance/summary?granularity=day|month|year
 * con un rango de fechas opcional. El backend devuelve:
 *   - gross_sales:    SUM(Order.total) en estados operativos
 *   - cogs:           SUM(OrderItem.unit_cost x qty) — snapshot al checkout
 *   - gross_margin:   gross_sales - cogs
 *   - operating_expenses, payroll
 *   - net_profit:     gross_margin - operating_expenses - payroll
 *   - timeseries[]:   misma agregacion por dia/mes/año
 *
 * ============================================================================
 * REPORTES EXPORTABLES
 * ============================================================================
 * - CSV: blob con BOM UTF-8 (Excel-friendly) que incluye KPIs, timeseries,
 *   top productos y gastos por tipo.
 * - PDF: abre una ventana HTML imprimible con CSS profesional (hero
 *   corporativo, A4, KPIs visuales, badge "Rentable"/"En perdidas"). El
 *   usuario imprime o guarda como PDF desde el dialogo del navegador.
 */
import { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line, CartesianGrid,
} from 'recharts';
import {
  Plus, Download, Users, DollarSign, Edit2, Trash2,
  TrendingDown, ShoppingCart, TrendingUp, Calendar, Filter,
} from 'lucide-react';
import api from '../api/client';
import AdminLayout from '../components/AdminLayout';
import Modal from '../components/Modal';
import Badge from '../components/Badge';
import { useToast } from '../context/ToastContext';
import {
  buildExpenseBreakdown,
  buildTopProducts,
} from '../utils/analytics';

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;
const PCT = (v) => `${Number(v || 0).toFixed(1)}%`;

const emptyEmployee = { name: '', document: '', position: '', salary: '', employment_status: 'active' };
const emptyExpense = { expense_type: '', description: '', amount: '', observation: '', expense_date: new Date().toISOString().slice(0, 10) };

const EXPENSE_TYPES = ['Arriendo', 'Servicios', 'Publicidad', 'Logística', 'Mantenimiento', 'Otro'];

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'employees', label: 'Empleados' },
  { id: 'expenses',  label: 'Gastos' },
];

const GRANULARITY = [
  { id: 'day',   label: 'Día' },
  { id: 'month', label: 'Mes' },
  { id: 'year',  label: 'Año' },
];

const PRESETS = [
  { id: 'today',     label: 'Hoy' },
  { id: 'week',      label: 'Últimos 7 días' },
  { id: 'month',     label: 'Mes en curso' },
  { id: 'quarter',   label: 'Trimestre' },
  { id: 'year',      label: 'Año en curso' },
  { id: 'all',       label: 'Todo' },
];

function presetRange(preset) {
  const today = new Date();
  const fmt = (d) => d.toISOString().slice(0, 10);
  const start = (d) => { d.setHours(0,0,0,0); return d; };
  if (preset === 'today') return { from: fmt(start(new Date())), to: fmt(today) };
  if (preset === 'week') {
    const d = new Date(); d.setDate(d.getDate() - 6);
    return { from: fmt(start(d)), to: fmt(today) };
  }
  if (preset === 'month') {
    const d = new Date(today.getFullYear(), today.getMonth(), 1);
    return { from: fmt(d), to: fmt(today) };
  }
  if (preset === 'quarter') {
    const d = new Date(); d.setMonth(d.getMonth() - 2); d.setDate(1);
    return { from: fmt(start(d)), to: fmt(today) };
  }
  if (preset === 'year') {
    const d = new Date(today.getFullYear(), 0, 1);
    return { from: fmt(d), to: fmt(today) };
  }
  return { from: '', to: '' };
}

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

function FinanceBreakdownChart({ summary }) {
  const data = [
    { name: 'COGS (costo productos)', value: summary.cogs,               fill: '#ef4444' },
    { name: 'Gastos operativos',      value: summary.operating_expenses, fill: '#f59e0b' },
    { name: 'Nómina',                 value: summary.payroll,            fill: '#8b5cf6' },
    { name: 'Utilidad neta',          value: Math.max(0, summary.net_profit), fill: '#1f7a5c' },
  ].filter((d) => d.value > 0);
  const total = data.reduce((s, d) => s + d.value, 0) || 1;

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const pct = (payload[0].value / total) * 100;
    return (
      <div style={{ background: '#fff', border: '1px solid #e1e5de', borderRadius: 8, padding: '0.6rem 1rem', fontSize: '0.8125rem', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
        <strong>{payload[0].name}</strong>
        <div>{COP(payload[0].value)} · {pct.toFixed(1)}%</div>
      </div>
    );
  };

  if (data.length === 0) return <div className="state" style={{ height: 220 }}>Sin datos para graficar</div>;

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="45%" innerRadius={60} outerRadius={90} paddingAngle={3}>
          {data.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend formatter={(value) => <span style={{ fontSize: '0.78rem', color: '#4c5960' }}>{value}</span>} />
      </PieChart>
    </ResponsiveContainer>
  );
}

function TimeseriesChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="state" style={{ height: 280 }}>Aún no hay datos en este periodo</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eaecea" />
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#4c5960' }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: '#9ca4a0' }} axisLine={false} tickLine={false} width={48}
               tickFormatter={(v) => `${(v/1000).toFixed(0)}k`} />
        <Tooltip
          formatter={(value, name) => [COP(value), name]}
          labelStyle={{ color: '#172026', fontWeight: 700 }}
        />
        <Legend formatter={(v) => <span style={{ fontSize: '0.78rem' }}>{v}</span>} />
        <Line type="monotone" dataKey="gross_sales"  name="Ventas" stroke="#1f7a5c" strokeWidth={2.5} dot={{ r: 4 }} />
        <Line type="monotone" dataKey="cogs"         name="COGS"   stroke="#ef4444" strokeWidth={2} dot={{ r: 3 }} />
        <Line type="monotone" dataKey="gross_margin" name="Margen" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function AdminFinance() {
  const toast = useToast();
  const [tab, setTab] = useState('dashboard');
  const [empModal, setEmpModal] = useState(false);
  const [expModal, setExpModal] = useState(false);
  const [editEmp, setEditEmp] = useState(null);
  const [editExp, setEditExp] = useState(null);
  const [empForm, setEmpForm] = useState(emptyEmployee);
  const [expForm, setExpForm] = useState(emptyExpense);
  const [loading, setLoading] = useState(false);

  // Filtros
  const [periodPreset, setPeriodPreset] = useState('month');
  const [granularity, setGranularity] = useState('month');
  const [periodFrom, setPeriodFrom] = useState(presetRange('month').from);
  const [periodTo, setPeriodTo] = useState(presetRange('month').to);

  // Data
  const [summary, setSummary] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [orders, setOrders] = useState([]);

  const buildQs = () => {
    const params = new URLSearchParams({ granularity });
    if (periodFrom) params.append('period_from', periodFrom);
    if (periodTo)   params.append('period_to', periodTo);
    return params.toString();
  };

  const loadAll = async () => {
    try {
      const [sumR, empR, expR, ordR] = await Promise.all([
        api.get(`/admin/finance/summary?${buildQs()}`),
        api.get('/admin/employees'),
        api.get('/admin/expenses'),
        api.get('/admin/orders'),
      ]);
      setSummary(sumR.data);
      setEmployees(empR.data || []);
      setExpenses(expR.data || []);
      setOrders(ordR.data || []);
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al cargar finanzas.', 'error');
    }
  };

  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, [periodFrom, periodTo, granularity]);

  const applyPreset = (id) => {
    setPeriodPreset(id);
    const range = presetRange(id);
    setPeriodFrom(range.from);
    setPeriodTo(range.to);
    // Granularidad sugerida segun preset
    if (id === 'today' || id === 'week') setGranularity('day');
    else if (id === 'year') setGranularity('month');
    else if (id === 'all') setGranularity('year');
  };

  const saveEmployee = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = { ...empForm, salary: Number(empForm.salary) };
      if (editEmp) {
        await api.put(`/admin/employees/${editEmp.id}`, payload);
        toast('Empleado actualizado.', 'success');
      } else {
        await api.post('/admin/employees', payload);
        toast('Empleado registrado.', 'success');
      }
      setEmpModal(false); setEditEmp(null); setEmpForm(emptyEmployee);
      loadAll();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al guardar empleado.', 'error');
    } finally { setLoading(false); }
  };

  const deactivateEmployee = async (id) => {
    await api.delete(`/admin/employees/${id}`).catch(() => {});
    toast('Empleado inactivado.', 'success');
    loadAll();
  };

  const saveExpense = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = { ...expForm, amount: Number(expForm.amount) };
      if (editExp) {
        await api.put(`/admin/expenses/${editExp.id}`, payload);
        toast('Gasto actualizado.', 'success');
      } else {
        await api.post('/admin/expenses', payload);
        toast('Gasto registrado.', 'success');
      }
      setExpModal(false); setEditExp(null); setExpForm(emptyExpense);
      loadAll();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al guardar gasto.', 'error');
    } finally { setLoading(false); }
  };

  const deleteExpense = async (id) => {
    await api.delete(`/admin/expenses/${id}`).catch(() => {});
    toast('Gasto eliminado.', 'success');
    loadAll();
  };

  const openReport = (format) => {
    if (!summary) return;
    const expenseBreakdown = buildExpenseBreakdown(expenses);
    const topProducts = buildTopProducts(orders, 8);
    const generatedAt = new Date().toLocaleString('es-CO');
    const periodLabel = periodFrom || periodTo
      ? `${periodFrom || '—'} a ${periodTo || '—'} · ${granularity}`
      : 'Todo el historial';

    const escapeHtml = (value) => String(value ?? '')
      .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;').replaceAll("'", '&#039;');

    if (format === 'csv') {
      const csvCell = (v) => `"${String(v ?? '').replaceAll('"', '""')}"`;
      const csvLine = (row) => row.map(csvCell).join(';');
      const rows = [
        ['Reporte financiero Distrito Urbano'],
        ['Periodo', periodLabel],
        ['Generado', generatedAt],
        [],
        ['KPI', 'Valor'],
        ['Ventas brutas', summary.gross_sales],
        ['Pedidos con venta', summary.orders_count],
        ['Ticket promedio', summary.avg_ticket],
        ['COGS', summary.cogs],
        ['Margen bruto', summary.gross_margin],
        ['Margen bruto %', summary.gross_margin_pct],
        ['Gastos operativos', summary.operating_expenses],
        ['Nomina activa', summary.payroll],
        ['Utilidad neta', summary.net_profit],
        ['Margen neto %', summary.net_margin_pct],
        [],
        ['Serie de ventas', 'Ventas', 'COGS', 'Margen bruto', 'Pedidos'],
        ...(summary.timeseries || []).map((t) =>
          [t.label, t.gross_sales, t.cogs, t.gross_margin, t.orders_count]),
        [],
        ['Productos mas vendidos', 'Unidades', 'Ingresos'],
        ...topProducts.map((p) => [p.product_name, p.quantity, p.revenue]),
        [],
        ['Gastos por tipo', 'Total'],
        ...expenseBreakdown.map((e) => [e.type, e.amount]),
      ];
      const csv = rows.map(csvLine).join('\n');
      const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `reporte_financiero_${(periodFrom || 'todo')}_${(periodTo || 'hoy')}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }

    // PDF imprimible "premium"
    const win = window.open('', '_blank');
    if (!win) { toast('El navegador bloqueó la ventana del reporte.', 'error'); return; }
    const tsRows = (summary.timeseries || []).map((t) =>
      `<tr><td>${escapeHtml(t.label)}</td>
           <td class="r">${COP(t.gross_sales)}</td>
           <td class="r">${COP(t.cogs)}</td>
           <td class="r"><strong>${COP(t.gross_margin)}</strong></td>
           <td class="r">${t.orders_count}</td></tr>`
    ).join('') || '<tr><td colspan="5" class="muted">Sin datos en el periodo</td></tr>';

    const topRows = topProducts.map((p, i) =>
      `<tr><td>${i + 1}</td><td>${escapeHtml(p.product_name)}</td>
           <td class="r">${p.quantity}</td><td class="r">${COP(p.revenue)}</td></tr>`
    ).join('') || '<tr><td colspan="4" class="muted">Sin ventas en el periodo</td></tr>';

    const expRows = expenseBreakdown.map((e) =>
      `<tr><td>${escapeHtml(e.type)}</td><td class="r">${COP(e.amount)}</td></tr>`
    ).join('') || '<tr><td colspan="2" class="muted">Sin gastos en el periodo</td></tr>';

    win.document.write(`<!doctype html>
    <html lang="es"><head><meta charset="utf-8"><title>Reporte financiero · Distrito Urbano</title>
    <style>
      @page { size: A4; margin: 14mm; }
      * { box-sizing: border-box; }
      body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; color: #172026; line-height: 1.45; margin: 0; padding: 24px; background: #fff; }
      .toolbar { display: flex; gap: 10px; justify-content: flex-end; margin-bottom: 24px; }
      .toolbar button { padding: 10px 18px; border: 1px solid #dfe5dc; border-radius: 8px; background: #1f7a5c; color: #fff; font-weight: 700; cursor: pointer; }
      .toolbar button.secondary { background: #fff; color: #172026; }
      .hero { display: flex; align-items: center; justify-content: space-between; padding: 20px 24px; background: linear-gradient(135deg,#1f7a5c 0%, #134e3a 100%); color: #fff; border-radius: 14px; margin-bottom: 28px; }
      .hero h1 { margin: 0; font-size: 26px; letter-spacing: -0.01em; }
      .hero .subtitle { font-size: 13px; opacity: 0.85; margin-top: 4px; }
      .hero .logo { width: 56px; height: 56px; border-radius: 12px; background: rgba(255,255,255,0.18); display: grid; place-items: center; font-size: 20px; font-weight: 800; }
      .section { margin-bottom: 22px; page-break-inside: avoid; }
      .section h2 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; color: #677067; margin: 0 0 10px; font-weight: 800; }
      .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
      .kpi { border: 1px solid #e6e9e3; border-radius: 10px; padding: 12px 14px; background: #fafbf9; }
      .kpi .lbl { font-size: 11px; color: #677067; text-transform: uppercase; font-weight: 700; letter-spacing: 0.04em; }
      .kpi .val { font-size: 19px; font-weight: 800; margin-top: 2px; }
      .kpi .sub { font-size: 11px; color: #677067; margin-top: 2px; }
      .kpi.green .val { color: #1f7a5c; }
      .kpi.red   .val { color: #b91c1c; }
      .kpi.blue  .val { color: #2563eb; }
      .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
      table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 12px; }
      th, td { border-bottom: 1px solid #eaecea; padding: 8px 10px; text-align: left; }
      th { background: #f5f7f2; font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; color: #4c5960; }
      td.r, th.r { text-align: right; font-variant-numeric: tabular-nums; }
      .muted { color: #9ca4a0; font-style: italic; padding: 16px; text-align: center; }
      .legend { display: flex; gap: 16px; margin-top: 10px; flex-wrap: wrap; font-size: 11px; color: #4c5960; }
      .legend span { display: inline-flex; align-items: center; gap: 5px; }
      .legend i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
      .footer { margin-top: 32px; padding-top: 14px; border-top: 1px solid #eaecea; font-size: 11px; color: #9ca4a0; display: flex; justify-content: space-between; }
      .pill { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 700; }
      .pill.green { background: #dcfce7; color: #166534; }
      .pill.red   { background: #fee2e2; color: #991b1b; }
      @media print { .toolbar { display: none; } body { padding: 0; } }
    </style></head><body>
      <div class="toolbar">
        <button class="secondary" onclick="window.close()">Cerrar</button>
        <button onclick="window.print()">Imprimir / Guardar PDF</button>
      </div>
      <div class="hero">
        <div>
          <h1>Reporte financiero</h1>
          <div class="subtitle">Distrito Urbano · ${escapeHtml(periodLabel)} · Generado ${escapeHtml(generatedAt)}</div>
        </div>
        <div class="logo">DU</div>
      </div>

      <div class="section">
        <h2>KPIs principales</h2>
        <div class="kpi-grid">
          <div class="kpi green"><div class="lbl">Ventas brutas</div><div class="val">${COP(summary.gross_sales)}</div><div class="sub">${summary.orders_count} pedidos</div></div>
          <div class="kpi blue"><div class="lbl">Ticket promedio</div><div class="val">${COP(summary.avg_ticket)}</div><div class="sub">por pedido</div></div>
          <div class="kpi red"><div class="lbl">COGS (costo)</div><div class="val">${COP(summary.cogs)}</div><div class="sub">costo de productos vendidos</div></div>
          <div class="kpi green"><div class="lbl">Margen bruto</div><div class="val">${COP(summary.gross_margin)}</div><div class="sub">${PCT(summary.gross_margin_pct)} sobre ventas</div></div>
        </div>
      </div>

      <div class="section">
        <h2>Resultado operativo</h2>
        <div class="kpi-grid">
          <div class="kpi"><div class="lbl">Gastos operativos</div><div class="val">${COP(summary.operating_expenses)}</div></div>
          <div class="kpi"><div class="lbl">Nómina activa</div><div class="val">${COP(summary.payroll)}</div></div>
          <div class="kpi ${summary.net_profit >= 0 ? 'green' : 'red'}">
            <div class="lbl">Utilidad neta</div>
            <div class="val">${COP(summary.net_profit)}</div>
            <div class="sub">${PCT(summary.net_margin_pct)} margen neto</div>
          </div>
          <div class="kpi"><div class="lbl">Estado</div>
            <div class="val">
              <span class="pill ${summary.net_profit >= 0 ? 'green' : 'red'}">
                ${summary.net_profit >= 0 ? 'Rentable' : 'En pérdidas'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="section">
        <h2>Evolución del periodo (${escapeHtml(granularity)})</h2>
        <table>
          <thead><tr><th>Periodo</th><th class="r">Ventas</th><th class="r">COGS</th><th class="r">Margen bruto</th><th class="r">Pedidos</th></tr></thead>
          <tbody>${tsRows}</tbody>
        </table>
      </div>

      <div class="grid-2">
        <div class="section">
          <h2>Productos más vendidos</h2>
          <table>
            <thead><tr><th>#</th><th>Producto</th><th class="r">Uds.</th><th class="r">Ingresos</th></tr></thead>
            <tbody>${topRows}</tbody>
          </table>
        </div>
        <div class="section">
          <h2>Gastos por tipo</h2>
          <table>
            <thead><tr><th>Tipo</th><th class="r">Total</th></tr></thead>
            <tbody>${expRows}</tbody>
          </table>
        </div>
      </div>

      <div class="footer">
        <span>Distrito Urbano · Reporte interno · Ingeniería de Software</span>
        <span>Documento generado automáticamente</span>
      </div>
    </body></html>`);
    win.document.close();
  };

  if (!summary) return <AdminLayout><div className="state">Cargando finanzas...</div></AdminLayout>;

  const expenseBreakdown = buildExpenseBreakdown(expenses);
  const topProducts = buildTopProducts(orders, 6);
  const isNegativeProfit = summary.net_profit < 0;

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <h1 className="page-title">Finanzas</h1>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary btn-sm" onClick={() => openReport('csv')}>
            <Download size={14} /> CSV
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => openReport('pdf')}>
            <Download size={14} /> Reporte PDF
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs-bar">
        {TABS.map((t) => (
          <button key={t.id} className={`tab-btn ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'dashboard' && (
        <div>
          {/* Filtros */}
          <div className="finance-filter-bar">
            <div className="finance-filter-section">
              <Filter size={14} color="var(--neutral-500)" />
              <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-600)' }}>Periodo:</span>
              {PRESETS.map((p) => (
                <button
                  key={p.id}
                  className={`filter-chip${periodPreset === p.id ? ' active' : ''}`}
                  onClick={() => applyPreset(p.id)}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="finance-filter-section">
              <Calendar size={14} color="var(--neutral-500)" />
              <input
                type="date" value={periodFrom}
                onChange={(e) => { setPeriodFrom(e.target.value); setPeriodPreset('custom'); }}
                style={{ width: 'auto', padding: '4px 8px', fontSize: '0.8125rem' }}
              />
              <span style={{ color: 'var(--neutral-500)' }}>→</span>
              <input
                type="date" value={periodTo}
                onChange={(e) => { setPeriodTo(e.target.value); setPeriodPreset('custom'); }}
                style={{ width: 'auto', padding: '4px 8px', fontSize: '0.8125rem' }}
              />
            </div>
            <div className="finance-filter-section">
              <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--neutral-600)' }}>Agrupar por:</span>
              {GRANULARITY.map((g) => (
                <button
                  key={g.id}
                  className={`filter-chip${granularity === g.id ? ' active' : ''}`}
                  onClick={() => setGranularity(g.id)}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>

          {isNegativeProfit && (
            <div className="alert error" style={{ marginBottom: '1.25rem' }}>
              <TrendingDown size={16} />
              <strong>Utilidad neta negativa:</strong> Los costos superan las ventas. Revisa gastos y nómina.
            </div>
          )}

          {/* KPIs grid */}
          <div className="kpi-grid" style={{ marginBottom: '1.5rem' }}>
            <KpiCard
              icon={<DollarSign size={22} />}
              label="Ventas brutas"
              value={COP(summary.gross_sales)}
              sub={`${summary.orders_count} pedidos · ${COP(summary.avg_ticket)} ticket`}
              color="green"
            />
            <KpiCard
              icon={<TrendingDown size={22} />}
              label="COGS (costos productos)"
              value={COP(summary.cogs)}
              sub="Costo materiales + envío de proveedor"
              color="red"
            />
            <KpiCard
              icon={<TrendingUp size={22} />}
              label="Margen bruto"
              value={COP(summary.gross_margin)}
              sub={`${PCT(summary.gross_margin_pct)} sobre ventas`}
              color="blue"
            />
            <KpiCard
              icon={<DollarSign size={22} />}
              label="Utilidad neta"
              value={COP(summary.net_profit)}
              sub={`Margen neto ${PCT(summary.net_margin_pct)}`}
              color={isNegativeProfit ? 'orange' : 'green'}
            />
          </div>

          {/* Timeseries */}
          <div className="chart-card" style={{ marginBottom: '1.5rem' }}>
            <div className="chart-title">
              Evolución de ventas, COGS y margen bruto
              <span style={{ fontSize: '0.8rem', color: '#9ca4a0', fontWeight: 400 }}>
                Por {granularity === 'day' ? 'día' : granularity === 'month' ? 'mes' : 'año'}
              </span>
            </div>
            <TimeseriesChart data={summary.timeseries} />
          </div>

          {/* Charts side by side */}
          <div className="charts-grid">
            <div className="chart-card">
              <div className="chart-title">Distribución financiera</div>
              <FinanceBreakdownChart summary={summary} />
            </div>
            <div className="chart-card">
              <div className="chart-title">
                Productos más vendidos
                <span style={{ fontSize: '0.8rem', color: '#9ca4a0', fontWeight: 400 }}>Por unidades</span>
              </div>
              {topProducts.length > 0 ? (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={topProducts} barCategoryGap="35%">
                    <XAxis dataKey="product_name" tick={{ fontSize: 11, fill: '#4c5960' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#9ca4a0' }} axisLine={false} tickLine={false} width={28} />
                    <Tooltip
                      formatter={(value, name, item) => name === 'quantity' ? `${value} uds` : COP(value)}
                    />
                    <Bar dataKey="quantity" fill="#1f7a5c" radius={[6,6,0,0]} name="Unidades" />
                  </BarChart>
                </ResponsiveContainer>
              ) : <div className="state" style={{ height: 240 }}>Sin ventas en el periodo</div>}
            </div>
          </div>

          {/* Tablas resumen */}
          <div className="grid-2-cards" style={{ marginTop: '1.5rem' }}>
            <div className="section-card">
              <div className="section-card-header">
                <span className="section-card-title">Detalle del periodo</span>
              </div>
              <div className="section-card-body" style={{ padding: 0 }}>
                <table className="data-table" style={{ fontSize: '0.875rem' }}>
                  <thead><tr><th>Periodo</th><th style={{textAlign:'right'}}>Ventas</th><th style={{textAlign:'right'}}>COGS</th><th style={{textAlign:'right'}}>Margen</th><th style={{textAlign:'right'}}>Pedidos</th></tr></thead>
                  <tbody>
                    {(summary.timeseries || []).length === 0 ? (
                      <tr><td colSpan={5} className="state">Sin datos</td></tr>
                    ) : summary.timeseries.map((t) => (
                      <tr key={t.label}>
                        <td><strong>{t.label}</strong></td>
                        <td style={{ textAlign: 'right' }}>{COP(t.gross_sales)}</td>
                        <td style={{ textAlign: 'right', color: 'var(--neutral-500)' }}>{COP(t.cogs)}</td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: t.gross_margin >= 0 ? 'var(--success-text)' : 'var(--error-text)' }}>
                          {COP(t.gross_margin)}
                        </td>
                        <td style={{ textAlign: 'right' }}>{t.orders_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="section-card">
              <div className="section-card-header">
                <span className="section-card-title">Gastos por tipo</span>
              </div>
              <div className="section-card-body" style={{ padding: 0 }}>
                <table className="data-table" style={{ fontSize: '0.875rem' }}>
                  <thead><tr><th>Tipo</th><th style={{textAlign:'right'}}>Total</th></tr></thead>
                  <tbody>
                    {expenseBreakdown.length === 0 ? (
                      <tr><td colSpan={2} className="state">Sin gastos registrados</td></tr>
                    ) : expenseBreakdown.map((e) => (
                      <tr key={e.type}>
                        <td><span className="category-chip">{e.type}</span></td>
                        <td style={{ textAlign: 'right', fontWeight: 700 }}>{COP(e.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Empleados */}
      {tab === 'employees' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <span style={{ color: '#677067', fontSize: '0.875rem' }}>{employees.filter((e) => e.employment_status === 'active').length} empleados activos · Nómina mensual: <strong>{COP(summary.payroll)}</strong></span>
            <button className="btn btn-primary btn-sm" onClick={() => { setEmpForm(emptyEmployee); setEditEmp(null); setEmpModal(true); }}>
              <Plus size={15} /> Registrar empleado
            </button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Nombre</th><th>Documento</th><th>Cargo</th><th>Salario</th><th>Estado</th><th style={{textAlign:'right'}}>Acciones</th></tr></thead>
              <tbody>
                {employees.map((emp) => (
                  <tr key={emp.id}>
                    <td><strong>{emp.name}</strong></td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8125rem' }}>{emp.document}</td>
                    <td>{emp.position}</td>
                    <td style={{ fontWeight: 700 }}>{COP(emp.salary)}/mes</td>
                    <td><Badge variant={emp.employment_status === 'active' ? 'success' : 'neutral'}>{emp.employment_status === 'active' ? 'Activo' : 'Inactivo'}</Badge></td>
                    <td>
                      <div className="table-actions" style={{ justifyContent: 'flex-end' }}>
                        <button className="btn btn-ghost btn-sm btn-icon" onClick={() => { setEditEmp(emp); setEmpForm({ name: emp.name, document: emp.document, position: emp.position, salary: emp.salary, employment_status: emp.employment_status }); setEmpModal(true); }}>
                          <Edit2 size={14} />
                        </button>
                        {emp.employment_status === 'active' && (
                          <button className="btn btn-danger btn-sm btn-icon" onClick={() => deactivateEmployee(emp.id)}>
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {employees.length === 0 && <tr><td colSpan={6} className="state">Sin empleados registrados</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Gastos */}
      {tab === 'expenses' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <span style={{ color: '#677067', fontSize: '0.875rem' }}>
              Total gastos: <strong style={{ color: '#172026' }}>{COP(expenses.reduce((s, e) => s + e.amount, 0))}</strong>
            </span>
            <button className="btn btn-primary btn-sm" onClick={() => { setExpForm(emptyExpense); setEditExp(null); setExpModal(true); }}>
              <Plus size={15} /> Registrar gasto
            </button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Tipo</th><th>Descripción</th><th>Fecha</th><th>Monto</th><th style={{textAlign:'right'}}>Acciones</th></tr></thead>
              <tbody>
                {expenses.map((exp) => (
                  <tr key={exp.id}>
                    <td><span className="category-chip">{exp.expense_type}</span></td>
                    <td style={{ color: '#677067' }}>{exp.description}</td>
                    <td style={{ fontSize: '0.8125rem', color: '#9ca4a0' }}>{exp.expense_date}</td>
                    <td style={{ fontWeight: 700 }}>{COP(exp.amount)}</td>
                    <td>
                      <div className="table-actions" style={{ justifyContent: 'flex-end' }}>
                        <button className="btn btn-ghost btn-sm btn-icon" onClick={() => { setEditExp(exp); setExpForm({ expense_type: exp.expense_type, description: exp.description, amount: exp.amount, observation: exp.observation || '', expense_date: exp.expense_date }); setExpModal(true); }}>
                          <Edit2 size={14} />
                        </button>
                        <button className="btn btn-danger btn-sm btn-icon" onClick={() => deleteExpense(exp.id)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {expenses.length === 0 && <tr><td colSpan={5} className="state">Sin gastos registrados</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal empleado */}
      <Modal
        open={empModal}
        onClose={() => setEmpModal(false)}
        title={editEmp ? 'Editar empleado' : 'Registrar empleado'}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setEmpModal(false)}>Cancelar</button>
            <button className="btn btn-primary" form="emp-form" type="submit" disabled={loading}>{editEmp ? 'Actualizar' : 'Guardar'}</button>
          </>
        }
      >
        <form id="emp-form" onSubmit={saveEmployee} style={{ display: 'grid', gap: '0.1rem' }}>
          <label>Nombre completo * <input value={empForm.name} onChange={(e) => setEmpForm({ ...empForm, name: e.target.value })} required /></label>
          <label>Documento * <input value={empForm.document} onChange={(e) => setEmpForm({ ...empForm, document: e.target.value })} required /></label>
          <label>Cargo * <input value={empForm.position} onChange={(e) => setEmpForm({ ...empForm, position: e.target.value })} required /></label>
          <label>Salario mensual (COP) * <input type="number" min="0" value={empForm.salary} onChange={(e) => setEmpForm({ ...empForm, salary: e.target.value })} required /></label>
          <label>Estado
            <select value={empForm.employment_status} onChange={(e) => setEmpForm({ ...empForm, employment_status: e.target.value })}>
              <option value="active">Activo</option>
              <option value="inactive">Inactivo</option>
            </select>
          </label>
        </form>
      </Modal>

      {/* Modal gasto */}
      <Modal
        open={expModal}
        onClose={() => setExpModal(false)}
        title={editExp ? 'Editar gasto' : 'Registrar gasto'}
        footer={
          <>
            <button className="btn btn-secondary" onClick={() => setExpModal(false)}>Cancelar</button>
            <button className="btn btn-primary" form="exp-form" type="submit" disabled={loading}>{editExp ? 'Actualizar' : 'Guardar'}</button>
          </>
        }
      >
        <form id="exp-form" onSubmit={saveExpense} style={{ display: 'grid', gap: '0.1rem' }}>
          <label>Tipo de gasto *
            <select value={expForm.expense_type} onChange={(e) => setExpForm({ ...expForm, expense_type: e.target.value })} required>
              <option value="">Selecciona tipo</option>
              {EXPENSE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>Descripción * <input value={expForm.description} onChange={(e) => setExpForm({ ...expForm, description: e.target.value })} required /></label>
          <label>Monto (COP) * <input type="number" min="0" value={expForm.amount} onChange={(e) => setExpForm({ ...expForm, amount: e.target.value })} required /></label>
          <label>Fecha * <input type="date" value={expForm.expense_date} onChange={(e) => setExpForm({ ...expForm, expense_date: e.target.value })} required /></label>
          <label>Observación <textarea value={expForm.observation} onChange={(e) => setExpForm({ ...expForm, observation: e.target.value })} /></label>
        </form>
      </Modal>
    </AdminLayout>
  );
}
