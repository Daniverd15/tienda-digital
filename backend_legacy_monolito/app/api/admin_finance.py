"""Rutas administrativas para finanzas, clientes y reportes del monolito.

Agrupa el tablero financiero del MVP inicial: ventas aprobadas, costo de
mercancia (COGS), nomina, gastos operativos, clientes, empleados y exportes.
En la version microservicios esta responsabilidad vive principalmente en
Commerce Service, pero este archivo sigue siendo referencia funcional de las
reglas contables implementadas en la primera entrega.
"""
import csv
from io import StringIO
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin
from app.api.orders import serialize_order
from app.core.database import get_db
from app.models import Employee, Expense, Order, OrderItem, ProductVariant, User
from app.schemas import ApiMessage, EmployeeIn, ExpenseIn
from app.services.audit_service import add_audit_log


router = APIRouter(prefix="/admin", tags=["Administracion financiera"])


def money(value) -> float:
    """Convierte Decimals/None a float para respuestas JSON del frontend."""
    return float(value or 0)


def finance_summary(db: Session) -> dict:
    """Calcula KPIs financieros agregados a partir de pedidos aprobados.

    Solo considera ordenes con pago aprobado para no inflar ingresos con
    pedidos pendientes o rechazados. A partir de esas ordenes estima COGS
    usando el costo de cada variante, descuenta nomina y gastos operativos,
    y devuelve datos listos para el dashboard.
    """
    approved_orders = (
        db.query(Order)
        .options(joinedload(Order.items).joinedload(OrderItem.variant))
        .filter(Order.payment_status == "aprobado")
        .all()
    )
    gross_sales = sum(Decimal(order.total) for order in approved_orders)
    cogs = sum(Decimal(item.variant.cost) * item.quantity for order in approved_orders for item in order.items)
    operating_costs = sum(Decimal(expense.amount) for expense in db.query(Expense).all())
    payroll = sum(Decimal(employee.salary) for employee in db.query(Employee).filter(Employee.employment_status == "active").all())
    net_profit = gross_sales - cogs - operating_costs - payroll
    sold_by_product: dict[str, int] = {}
    for order in approved_orders:
        for item in order.items:
            sold_by_product[item.product_name] = sold_by_product.get(item.product_name, 0) + item.quantity
    stock_total = sum(variant.stock for variant in db.query(ProductVariant).all()) or 1
    sold_total = sum(sold_by_product.values())
    return {
        "ventas_brutas": money(gross_sales),
        "cogs": money(cogs),
        "costos_operativos": money(operating_costs),
        "nomina": money(payroll),
        "utilidad_neta": money(net_profit),
        "productos_mas_vendidos": sorted(
            [{"product_name": name, "quantity": qty} for name, qty in sold_by_product.items()],
            key=lambda item: item["quantity"],
            reverse=True,
        )[:5],
        "rotacion_inventario": round(sold_total / stock_total, 4),
        "ordenes_aprobadas": len(approved_orders),
    }


def serialize_employee(employee: Employee) -> dict:
    """Normaliza empleados para las tablas de administracion."""
    return {
        "id": employee.id,
        "name": employee.name,
        "document": employee.document,
        "position": employee.position,
        "salary": money(employee.salary),
        "employment_status": employee.employment_status,
    }


def serialize_expense(expense: Expense) -> dict:
    """Normaliza gastos operativos para listados, edicion y reportes."""
    return {
        "id": expense.id,
        "expense_type": expense.expense_type,
        "description": expense.description,
        "amount": money(expense.amount),
        "observation": expense.observation,
        "expense_date": expense.expense_date,
        "created_by": expense.created_by,
        "created_at": expense.created_at,
    }


@router.get("/customers")
def customers(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Lista clientes registrados para gestion comercial y soporte."""
    users = db.query(User).filter(User.role == "customer").order_by(User.created_at.desc()).all()
    return [{"id": user.id, "name": user.name, "email": user.email, "phone": user.phone, "active": user.active} for user in users]


@router.patch("/customers/{customer_id}/status")
def update_customer_status(customer_id: int, active: bool, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Activa o desactiva un cliente sin borrar su historial de compras."""
    customer = db.query(User).filter(User.id == customer_id, User.role == "customer").first()
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    previous = {"active": customer.active}
    customer.active = active
    add_audit_log(db, user_id=admin.id, action="update_customer_status", entity="users", entity_id=customer.id, previous_value=previous, new_value={"active": active})
    db.commit()
    return {"id": customer.id, "name": customer.name, "email": customer.email, "phone": customer.phone, "active": customer.active}


@router.get("/customers/{customer_id}/orders")
def customer_orders(customer_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Consulta pedidos de un cliente para revision administrativa."""
    orders = db.query(Order).options(joinedload(Order.items), joinedload(Order.payments)).filter(Order.user_id == customer_id).all()
    return [serialize_order(order) for order in orders]


@router.get("/employees")
def employees(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Lista empleados usados para calcular el rubro de nomina."""
    return [serialize_employee(employee) for employee in db.query(Employee).order_by(Employee.id.desc()).all()]


@router.post("/employees", status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Crea un empleado y lo incorpora al calculo de nomina si esta activo."""
    employee = Employee(**payload.model_dump())
    db.add(employee)
    db.flush()
    add_audit_log(db, user_id=admin.id, action="create_employee", entity="employees", entity_id=employee.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(employee)
    return serialize_employee(employee)


@router.put("/employees/{employee_id}")
def update_employee(employee_id: int, payload: EmployeeIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Actualiza datos laborales y salariales de un empleado."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")
    previous = serialize_employee(employee)
    for field, value in payload.model_dump().items():
        setattr(employee, field, value)
    add_audit_log(db, user_id=admin.id, action="update_employee", entity="employees", entity_id=employee.id, previous_value=previous, new_value=payload.model_dump())
    db.commit()
    return serialize_employee(employee)


@router.delete("/employees/{employee_id}", response_model=ApiMessage)
def delete_employee(employee_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Inactiva un empleado para excluirlo de la nomina futura."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")
    employee.employment_status = "inactive"
    add_audit_log(db, user_id=admin.id, action="deactivate_employee", entity="employees", entity_id=employee.id)
    db.commit()
    return ApiMessage(message="Empleado inactivado.")


@router.get("/expenses")
def expenses(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Lista gastos operativos ordenados por fecha de ocurrencia."""
    return [serialize_expense(expense) for expense in db.query(Expense).order_by(Expense.expense_date.desc()).all()]


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Registra un gasto operativo asociado al administrador creador."""
    expense = Expense(**payload.model_dump(), created_by=admin.id)
    db.add(expense)
    db.flush()
    add_audit_log(db, user_id=admin.id, action="create_expense", entity="expenses", entity_id=expense.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(expense)
    return serialize_expense(expense)


@router.put("/expenses/{expense_id}")
def update_expense(expense_id: int, payload: ExpenseIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Edita un gasto y conserva valores previos en auditoria."""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado.")
    previous = serialize_expense(expense)
    for field, value in payload.model_dump().items():
        setattr(expense, field, value)
    add_audit_log(db, user_id=admin.id, action="update_expense", entity="expenses", entity_id=expense.id, previous_value=previous, new_value=payload.model_dump())
    db.commit()
    return serialize_expense(expense)


@router.delete("/expenses/{expense_id}", response_model=ApiMessage)
def delete_expense(expense_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Elimina un gasto cargado por error y audita la accion."""
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado.")
    db.delete(expense)
    add_audit_log(db, user_id=admin.id, action="delete_expense", entity="expenses", entity_id=expense_id)
    db.commit()
    return ApiMessage(message="Gasto eliminado.")


@router.get("/finance/summary")
def finance(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Expone el resumen financiero crudo para componentes del admin."""
    return finance_summary(db)


@router.get("/dashboard")
def dashboard(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Compone KPIs y conteos por estado para la pantalla principal admin."""
    summary = finance_summary(db)
    return {
        **summary,
        "ventas_por_periodo": [{"period": "actual", "amount": summary["ventas_brutas"]}],
        "pedidos_por_estado": [
            {"status": status_name, "count": db.query(Order).filter(Order.status == status_name).count()}
            for status_name in ["pendiente_pago", "preparacion", "enviado", "entregado", "rechazado"]
        ],
    }


@router.get("/reports/export/csv")
def export_csv(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Genera un CSV liviano con los indicadores financieros actuales."""
    summary = finance_summary(db)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Indicador", "Valor"])
    for key, value in summary.items():
        if key != "productos_mas_vendidos":
            writer.writerow([key, value])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reportes_financieros.csv"},
    )


@router.get("/reports/export/pdf")
def export_pdf(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Devuelve HTML imprimible para exportar el reporte financiero a PDF."""
    summary = finance_summary(db)
    top = "".join(
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #e5e7eb'><strong>#{i+1}</strong> {p['product_name']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:right'>{p['quantity']} uds</td></tr>"
        for i, p in enumerate(summary.get("productos_mas_vendidos", []))
    )
    labels = {
        "ventas_brutas": "Ventas brutas", "cogs": "COGS", "costos_operativos": "Costos operativos",
        "nomina": "Nómina", "utilidad_neta": "Utilidad neta", "rotacion_inventario": "Rotación inventario",
        "ordenes_aprobadas": "Órdenes aprobadas",
    }
    rows = "".join(
        f"<tr><td style='padding:10px 16px;border-bottom:1px solid #e5e7eb'>{labels.get(k, k)}</td>"
        f"<td style='padding:10px 16px;border-bottom:1px solid #e5e7eb;text-align:right;font-weight:700'>{v}</td></tr>"
        for k, v in summary.items() if k != "productos_mas_vendidos"
    )
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Reporte Financiero — Distrito Urbano</title>
  <style>
    body{{font-family:system-ui,sans-serif;margin:0;padding:2rem;color:#172026;background:#fff}}
    h1{{font-size:1.5rem;margin-bottom:0.25rem}}
    .subtitle{{color:#677067;font-size:0.875rem;margin-bottom:2rem}}
    table{{width:100%;border-collapse:collapse;margin-bottom:2rem}}
    th{{background:#f8f9f7;padding:10px 16px;text-align:left;font-size:0.75rem;letter-spacing:.05em;text-transform:uppercase;color:#677067;border-bottom:2px solid #e1e5de}}
    @media print{{.no-print{{display:none}}}}
  </style>
</head>
<body>
  <h1>Reporte Financiero</h1>
  <div class="subtitle">Distrito Urbano — generado el {__import__('datetime').date.today()}</div>
  <button class="no-print" onclick="window.print()" style="margin-bottom:1.5rem;padding:.6rem 1.2rem;background:#1f7a5c;color:#fff;border:none;border-radius:8px;font-size:.875rem;font-weight:700;cursor:pointer">
    Descargar PDF
  </button>
  <table><thead><tr><th>Indicador</th><th style="text-align:right">Valor</th></tr></thead><tbody>{rows}</tbody></table>
  <h2 style="font-size:1rem;margin-bottom:.75rem">Productos más vendidos</h2>
  <table><thead><tr><th>Producto</th><th style="text-align:right">Unidades</th></tr></thead><tbody>{top}</tbody></table>
  <script>window.addEventListener('load',function(){{window.print();}})</script>
</body>
</html>"""
    return Response(content=html, media_type="text/html")

