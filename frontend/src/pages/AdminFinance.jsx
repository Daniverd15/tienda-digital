import { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { Plus, Download, Users, DollarSign, Edit2, Trash2, TrendingDown } from 'lucide-react';
import api from '../api/client';
import { useAsync } from '../hooks/useAsync';
import AdminLayout from '../components/AdminLayout';
import Modal from '../components/Modal';
import Badge from '../components/Badge';
import { useToast } from '../context/ToastContext';

const COP = (v) => `$${Number(v || 0).toLocaleString('es-CO')}`;

const emptyEmployee = { name: '', document: '', position: '', salary: '', employment_status: 'active' };
const emptyExpense = { expense_type: '', description: '', amount: '', observation: '', expense_date: new Date().toISOString().slice(0, 10) };

const EXPENSE_TYPES = ['Arriendo', 'Servicios', 'Publicidad', 'Logística', 'Mantenimiento', 'Otro'];

const FINANCE_COLORS = ['#1f7a5c', '#ef4444', '#f59e0b', '#8b5cf6'];

function FinanceBreakdownChart({ dash }) {
  const data = [
    { name: 'COGS',         value: dash.cogs,             fill: '#ef4444' },
    { name: 'Costos op.',   value: dash.costos_operativos, fill: '#f59e0b' },
    { name: 'Nómina',       value: dash.nomina,            fill: '#8b5cf6' },
    { name: 'Utilidad',     value: Math.max(0, dash.utilidad_neta), fill: '#1f7a5c' },
  ].filter((d) => d.value > 0);

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{ background: '#fff', border: '1px solid #e1e5de', borderRadius: 8, padding: '0.65rem 1rem', fontSize: '0.8125rem', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
        <strong>{payload[0].name}</strong>: {COP(payload[0].value)}
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="45%" innerRadius={55} outerRadius={80} paddingAngle={3}>
          {data.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend formatter={(value) => <span style={{ fontSize: '0.78rem', color: '#4c5960' }}>{value}</span>} />
      </PieChart>
    </ResponsiveContainer>
  );
}

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'employees', label: 'Empleados' },
  { id: 'expenses',  label: 'Gastos' },
];

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

  // Mapeo: /admin/finance/summary (microservicios) -> formato dashboard del monolito.
  // Los campos que no calcula el summary (cogs, productos top, rotacion) van a 0 / [].
  const summaryToDash = (s) => ({
    ventas_brutas:        s.gross_sales || 0,
    ordenes_aprobadas:    s.orders_count || 0,
    cogs:                 0,
    costos_operativos:    s.operating_expenses || 0,
    nomina:               s.payroll || 0,
    utilidad_neta:        s.net_profit || 0,
    rotacion_inventario:  0,
    pedidos_por_estado:   [],
    productos_mas_vendidos: [],
  });

  const { data, setData } = useAsync(async () => {
    const [sumR, empR, expR] = await Promise.all([
      api.get('/admin/finance/summary'),
      api.get('/admin/employees'),
      api.get('/admin/expenses'),
    ]);
    return { dash: summaryToDash(sumR.data), employees: empR.data, expenses: expR.data };
  }, []);

  const reload = async () => {
    const [sumR, empR, expR] = await Promise.all([
      api.get('/admin/finance/summary'),
      api.get('/admin/employees'),
      api.get('/admin/expenses'),
    ]);
    setData({ dash: summaryToDash(sumR.data), employees: empR.data, expenses: expR.data });
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
      setEmpModal(false);
      setEditEmp(null);
      setEmpForm(emptyEmployee);
      reload();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al guardar empleado.', 'error');
    } finally { setLoading(false); }
  };

  const deactivateEmployee = async (id) => {
    await api.delete(`/admin/employees/${id}`).catch(() => {});
    toast('Empleado inactivado.', 'success');
    reload();
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
      setExpModal(false);
      setEditExp(null);
      setExpForm(emptyExpense);
      reload();
    } catch (err) {
      toast(err.response?.data?.detail || 'Error al guardar gasto.', 'error');
    } finally { setLoading(false); }
  };

  const deleteExpense = async (id) => {
    await api.delete(`/admin/expenses/${id}`).catch(() => {});
    toast('Gasto eliminado.', 'success');
    reload();
  };

  const openReport = async (format) => {
    // /admin/reports/export/{csv,pdf} NO existe en arquitectura de microservicios MVP.
    // En su lugar generamos el reporte en cliente desde data.dash + data.expenses.
    try {
      if (format === 'csv') {
        const rows = [
          ['Concepto', 'Valor'],
          ['Ventas brutas',    data.dash.ventas_brutas],
          ['Pedidos aprobados', data.dash.ordenes_aprobadas],
          ['COGS',             data.dash.cogs],
          ['Costos operativos', data.dash.costos_operativos],
          ['Nomina',           data.dash.nomina],
          ['Utilidad neta',    data.dash.utilidad_neta],
        ];
        const csv = rows.map((r) => r.join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'reporte_financiero.csv';
        a.click();
        URL.revokeObjectURL(url);
      } else {
        const win = window.open('', '_blank');
        win.document.write(`
          <html><head><title>Reporte financiero</title>
          <style>body{font-family:sans-serif;padding:2rem}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px}</style>
          </head><body>
          <h1>Reporte financiero</h1>
          <table>
            <tr><td>Ventas brutas</td><td>$${data.dash.ventas_brutas.toLocaleString('es-CO')}</td></tr>
            <tr><td>Pedidos aprobados</td><td>${data.dash.ordenes_aprobadas}</td></tr>
            <tr><td>Costos operativos</td><td>$${data.dash.costos_operativos.toLocaleString('es-CO')}</td></tr>
            <tr><td>Nomina</td><td>$${data.dash.nomina.toLocaleString('es-CO')}</td></tr>
            <tr><td><strong>Utilidad neta</strong></td><td><strong>$${data.dash.utilidad_neta.toLocaleString('es-CO')}</strong></td></tr>
          </table>
          <p style="margin-top:2rem;color:#666">Generado por Tienda Digital - Fase 2 microservicios.</p>
          </body></html>`);
        win.document.close();
      }
    } catch {
      toast('Error al generar el reporte.', 'error');
    }
  };

  if (!data) return <AdminLayout><div className="state">Cargando finanzas...</div></AdminLayout>;

  const { dash, employees, expenses } = data;

  const utilidadNegativa = dash.utilidad_neta < 0;

  return (
    <AdminLayout>
      <div className="page-header">
        <div className="page-header-left">
          <span className="page-eyebrow">RF-08</span>
          <h1 className="page-title">Finanzas</h1>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary btn-sm" onClick={() => openReport('csv')}>
            <Download size={14} /> CSV
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => openReport('pdf')}>
            <Download size={14} /> PDF imprimible
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

      {/* ── Dashboard tab ── */}
      {tab === 'dashboard' && (
        <div>
          {utilidadNegativa && (
            <div className="alert error" style={{ marginBottom: '1.25rem' }}>
              <TrendingDown size={16} />
              <strong>Utilidad neta negativa:</strong> Los costos superan las ventas brutas. Revisa gastos y nómina.
            </div>
          )}

          {/* KPIs */}
          <div className="kpi-grid" style={{ marginBottom: '1.5rem' }}>
            {[
              { label: 'Ventas brutas', value: COP(dash.ventas_brutas), color: 'green', icon: <DollarSign size={20} /> },
              { label: 'COGS', value: COP(dash.cogs), color: 'orange', icon: <DollarSign size={20} /> },
              { label: 'Costos operativos', value: COP(dash.costos_operativos), color: 'orange', icon: <DollarSign size={20} /> },
              { label: 'Nómina activa', value: COP(dash.nomina), color: 'purple', icon: <Users size={20} /> },
              { label: 'Utilidad neta', value: COP(dash.utilidad_neta), color: utilidadNegativa ? 'orange' : 'green', icon: <DollarSign size={20} /> },
            ].map(({ label, value, color, icon }) => (
              <div key={label} className={`kpi-card kpi-${color}`}>
                <div className="kpi-icon">{icon}</div>
                <div className="kpi-body">
                  <div className="kpi-label">{label}</div>
                  <div className="kpi-value">{value}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="charts-grid">
            {/* Products sold */}
            <div className="chart-card">
              <div className="chart-title">Productos más vendidos</div>
              {dash.productos_mas_vendidos?.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={dash.productos_mas_vendidos} barCategoryGap="35%">
                    <XAxis dataKey="product_name" tick={{ fontSize: 11, fill: '#4c5960' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#9ca4a0' }} axisLine={false} tickLine={false} width={24} />
                    <Tooltip />
                    <Bar dataKey="quantity" fill="#1f7a5c" radius={[6,6,0,0]} name="Unidades" />
                  </BarChart>
                </ResponsiveContainer>
              ) : <div className="state" style={{ height: 220 }}>Sin ventas</div>}
            </div>

            {/* Finance breakdown */}
            <div className="chart-card">
              <div className="chart-title">Distribución financiera</div>
              <FinanceBreakdownChart dash={dash} />
            </div>
          </div>

          {/* Top products table */}
          {dash.productos_mas_vendidos?.length > 0 && (
            <div className="table-wrap" style={{ marginTop: '1.5rem' }}>
              <table className="data-table">
                <thead><tr><th>#</th><th>Producto</th><th style={{textAlign:'right'}}>Unidades vendidas</th></tr></thead>
                <tbody>
                  {dash.productos_mas_vendidos.map((p, i) => (
                    <tr key={p.product_name}>
                      <td style={{ color: '#9ca4a0', fontSize: '0.8125rem' }}>#{i + 1}</td>
                      <td><strong>{p.product_name}</strong></td>
                      <td style={{ textAlign: 'right', fontWeight: 800 }}>{p.quantity} uds</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Employees tab ── */}
      {tab === 'employees' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <span style={{ color: '#677067', fontSize: '0.875rem' }}>{employees.filter((e) => e.employment_status === 'active').length} empleados activos</span>
            <button className="btn btn-primary btn-sm" onClick={() => { setEmpForm(emptyEmployee); setEditEmp(null); setEmpModal(true); }}>
              <Plus size={15} /> Registrar empleado
            </button>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>Nombre</th><th>Documento</th><th>Cargo</th><th>Salario</th><th>Estado</th><th style={{textAlign:'right'}}>Acciones</th></tr>
              </thead>
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

      {/* ── Expenses tab ── */}
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

      {/* Employee modal */}
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

      {/* Expense modal */}
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
