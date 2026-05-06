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
    return float(value or 0)


def finance_summary(db: Session) -> dict:
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
    return {
        "id": employee.id,
        "name": employee.name,
        "document": employee.document,
        "position": employee.position,
        "salary": money(employee.salary),
        "employment_status": employee.employment_status,
    }


def serialize_expense(expense: Expense) -> dict:
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
    users = db.query(User).filter(User.role == "customer").order_by(User.created_at.desc()).all()
    return [{"id": user.id, "name": user.name, "email": user.email, "phone": user.phone, "active": user.active} for user in users]


@router.get("/customers/{customer_id}/orders")
def customer_orders(customer_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    orders = db.query(Order).options(joinedload(Order.items), joinedload(Order.payments)).filter(Order.user_id == customer_id).all()
    return [serialize_order(order) for order in orders]


@router.get("/employees")
def employees(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [serialize_employee(employee) for employee in db.query(Employee).order_by(Employee.id.desc()).all()]


@router.post("/employees", status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    employee = Employee(**payload.model_dump())
    db.add(employee)
    db.flush()
    add_audit_log(db, user_id=admin.id, action="create_employee", entity="employees", entity_id=employee.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(employee)
    return serialize_employee(employee)


@router.put("/employees/{employee_id}")
def update_employee(employee_id: int, payload: EmployeeIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Empleado no encontrado.")
    employee.employment_status = "inactive"
    add_audit_log(db, user_id=admin.id, action="deactivate_employee", entity="employees", entity_id=employee.id)
    db.commit()
    return ApiMessage(message="Empleado inactivado.")


@router.get("/expenses")
def expenses(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [serialize_expense(expense) for expense in db.query(Expense).order_by(Expense.expense_date.desc()).all()]


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    expense = Expense(**payload.model_dump(), created_by=admin.id)
    db.add(expense)
    db.flush()
    add_audit_log(db, user_id=admin.id, action="create_expense", entity="expenses", entity_id=expense.id, new_value=payload.model_dump())
    db.commit()
    db.refresh(expense)
    return serialize_expense(expense)


@router.put("/expenses/{expense_id}")
def update_expense(expense_id: int, payload: ExpenseIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Gasto no encontrado.")
    db.delete(expense)
    add_audit_log(db, user_id=admin.id, action="delete_expense", entity="expenses", entity_id=expense_id)
    db.commit()
    return ApiMessage(message="Gasto eliminado.")


@router.get("/finance/summary")
def finance(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return finance_summary(db)


@router.get("/dashboard")
def dashboard(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    summary = finance_summary(db)
    rows = "".join(f"<tr><td>{key}</td><td>{value}</td></tr>" for key, value in summary.items() if key != "productos_mas_vendidos")
    html = f"""
    <html><head><title>Reporte financiero</title></head>
    <body>
      <h1>Reporte financiero imprimible</h1>
      <p>Alternativa local documentada para exportacion PDF: usar imprimir como PDF del navegador.</p>
      <table border="1" cellpadding="8">{rows}</table>
    </body></html>
    """
    return Response(content=html, media_type="text/html")

