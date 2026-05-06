import { useEffect, useState } from 'react';
import api from '../api/client';

const emptyEmployee = { name: '', document: '', position: '', salary: '', employment_status: 'active' };
const emptyExpense = {
  expense_type: '',
  description: '',
  amount: '',
  observation: '',
  expense_date: new Date().toISOString().slice(0, 10)
};

export default function AdminFinance() {
  const [dashboard, setDashboard] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [employeeForm, setEmployeeForm] = useState(emptyEmployee);
  const [expenseForm, setExpenseForm] = useState(emptyExpense);

  const load = async () => {
    const [dashboardRes, employeesRes, expensesRes, customersRes] = await Promise.all([
      api.get('/admin/dashboard'),
      api.get('/admin/employees'),
      api.get('/admin/expenses'),
      api.get('/admin/customers')
    ]);
    setDashboard(dashboardRes.data);
    setEmployees(employeesRes.data);
    setExpenses(expensesRes.data);
    setCustomers(customersRes.data);
  };

  useEffect(() => {
    load();
  }, []);

  const createEmployee = async (event) => {
    event.preventDefault();
    await api.post('/admin/employees', { ...employeeForm, salary: Number(employeeForm.salary) });
    setEmployeeForm(emptyEmployee);
    load();
  };

  const createExpense = async (event) => {
    event.preventDefault();
    await api.post('/admin/expenses', { ...expenseForm, amount: Number(expenseForm.amount) });
    setExpenseForm(emptyExpense);
    load();
  };

  const openReport = async (format) => {
    const { data } = await api.get(`/admin/reports/export/${format}`, {
      responseType: format === 'csv' ? 'blob' : 'text'
    });
    const blob = format === 'csv'
      ? data
      : new Blob([data], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  if (!dashboard) return <div className="state">Cargando finanzas...</div>;

  return (
    <main className="page-shell admin-grid-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">RF-08</span>
          <h1>Dashboard financiero</h1>
        </div>
        <div className="nav-actions">
          <button className="primary-button" onClick={() => openReport('csv')}>CSV</button>
          <button className="primary-button" onClick={() => openReport('pdf')}>PDF local</button>
        </div>
      </div>
      <section className="metric-grid">
        {[
          ['Ventas brutas', dashboard.ventas_brutas],
          ['COGS', dashboard.cogs],
          ['Costos operativos', dashboard.costos_operativos],
          ['Nomina', dashboard.nomina],
          ['Utilidad neta', dashboard.utilidad_neta],
          ['Rotacion inventario', dashboard.rotacion_inventario]
        ].map(([label, value]) => (
          <article className="metric-card" key={label}>
            <span>{label}</span>
            <strong>{typeof value === 'number' && label !== 'Rotacion inventario' ? `$${value.toLocaleString('es-CO')}` : value}</strong>
          </article>
        ))}
      </section>
      <section className="admin-section">
        <form onSubmit={createEmployee}>
          <h2>Empleados</h2>
          {Object.keys(emptyEmployee).map((field) => (
            <input key={field} placeholder={field} value={employeeForm[field]} onChange={(event) => setEmployeeForm({ ...employeeForm, [field]: event.target.value })} required />
          ))}
          <button className="primary-button">Registrar empleado</button>
        </form>
        <div className="table-list">
          {employees.map((employee) => (
            <article className="row-card" key={employee.id}>
              <strong>{employee.name}</strong>
              <span>{employee.position}</span>
              <span>{employee.employment_status}</span>
              <span>${Number(employee.salary).toLocaleString('es-CO')}</span>
            </article>
          ))}
        </div>
      </section>
      <section className="admin-section">
        <form onSubmit={createExpense}>
          <h2>Gastos</h2>
          {Object.keys(emptyExpense).map((field) => (
            <input
              key={field}
              type={field.includes('date') ? 'date' : field === 'amount' ? 'number' : 'text'}
              placeholder={field}
              value={expenseForm[field]}
              onChange={(event) => setExpenseForm({ ...expenseForm, [field]: event.target.value })}
              required={!['observation'].includes(field)}
            />
          ))}
          <button className="primary-button">Registrar gasto</button>
        </form>
        <div className="table-list">
          {expenses.map((expense) => (
            <article className="row-card" key={expense.id}>
              <strong>{expense.expense_type}</strong>
              <span>{expense.description}</span>
              <span>{expense.expense_date}</span>
              <span>${Number(expense.amount).toLocaleString('es-CO')}</span>
            </article>
          ))}
        </div>
      </section>
      <section className="admin-section">
        <div className="summary-panel">
          <h2>Productos mas vendidos</h2>
          {dashboard.productos_mas_vendidos.map((product) => (
            <span key={product.product_name}>{product.product_name}: {product.quantity}</span>
          ))}
        </div>
        <div className="table-list">
          <h2>Clientes</h2>
          {customers.map((customer) => (
            <article className="row-card" key={customer.id}>
              <strong>{customer.name}</strong>
              <span>{customer.email}</span>
              <span>{customer.phone}</span>
              <span>{customer.active ? 'Activo' : 'Inactivo'}</span>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
