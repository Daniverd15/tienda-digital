"""Endpoints administrativos del Commerce.

Cubre: pedidos (cambio de estado), empleados, gastos, finanzas, reviews y audit.
En la evolucion futura del MVP estos modulos saldran a Finance/Audit services.
"""
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import current_user_id, get_correlation_id, require_admin
from app.models import (
    Employee,
    Expense,
    Notification,
    Order,
    OrderAuditLog,
    OrderStatusHistory,
    Review,
)
from app.schemas import (
    ApiMessage,
    EmployeePublic,
    EmployeeUpsert,
    ExpensePublic,
    ExpenseUpsert,
    FinanceSummary,
    OrderAuditLogPublic,
    OrderStatusUpdate,
    ReviewPublic,
)
from app.api.orders import _serialize_order
from app.services.mailer import send_email


router = APIRouter(prefix="/admin", tags=["Administracion commerce"])


# -----------------------------------------------------------------------------
# Pedidos: lista admin + cambio de estado
# -----------------------------------------------------------------------------


VALID_ADMIN_TRANSITIONS = {
    "PAID":            {"EN_PREPARACION", "CANCELADA"},
    "EN_PREPARACION":  {"ENVIADO", "CANCELADA"},
    "ENVIADO":         {"ENTREGADO"},
}


@router.get("/orders")
def admin_list_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    user_id_filter: int | None = Query(default=None, alias="user_id"),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Order).options(joinedload(Order.items), joinedload(Order.history))
    if status_filter:
        q = q.filter(Order.status == status_filter)
    if user_id_filter:
        q = q.filter(Order.user_id == user_id_filter)
    rows = q.order_by(Order.created_at.desc()).limit(500).all()
    return [_serialize_order(o, include_history=False) for o in rows]


@router.get("/orders/{order_id}")
def admin_get_order(
    order_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    o = (
        db.query(Order)
        .options(joinedload(Order.items), joinedload(Order.history))
        .filter(Order.id == order_id)
        .first()
    )
    if not o:
        raise HTTPException(404, "Pedido no encontrado.")
    return _serialize_order(o, include_history=True)


@router.patch("/orders/{order_id}/status")
def admin_update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    admin_id: int = Depends(current_user_id),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    o = db.query(Order).filter(Order.id == order_id).first()
    if not o:
        raise HTTPException(404, "Pedido no encontrado.")
    allowed = VALID_ADMIN_TRANSITIONS.get(o.status, set())
    if payload.new_status not in allowed:
        raise HTTPException(
            409,
            f"Transicion invalida: {o.status} -> {payload.new_status}. Permitidas desde {o.status}: {sorted(allowed)}",
        )
    prev = o.status
    o.status = payload.new_status
    db.add(OrderStatusHistory(
        order_id=o.id, from_status=prev, to_status=payload.new_status,
        changed_by=admin_id, notes=payload.notes or "Cambio administrativo",
    ))
    db.add(OrderAuditLog(
        order_id=o.id, action=f"status_change_{prev}_to_{payload.new_status}",
        performed_by=admin_id, details=payload.notes or "", correlation_id=correlation_id,
    ))
    # Notificar al cliente
    titles = {
        "EN_PREPARACION": "Tu pedido esta en preparacion",
        "ENVIADO":        "Tu pedido fue despachado",
        "ENTREGADO":      "Tu pedido fue entregado",
        "CANCELADA":      "Tu pedido fue cancelado",
    }
    title = titles.get(payload.new_status, "Cambio en tu pedido")
    msg = f"El pedido {o.order_code} ahora esta {payload.new_status}."
    db.add(Notification(user_id=o.user_id, order_id=o.id, title=title, message=msg))
    db.commit()
    send_email(o.contact_email, title, msg)
    return {"order_id": o.id, "status": o.status, "message": title}


# -----------------------------------------------------------------------------
# Empleados
# -----------------------------------------------------------------------------


@router.get("/employees", response_model=list[EmployeePublic])
def list_employees(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(Employee).order_by(Employee.id.desc()).all()


@router.post("/employees", response_model=EmployeePublic, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeUpsert, _: dict = Depends(require_admin),
                    db: Session = Depends(get_db)):
    if db.query(Employee).filter(Employee.document == payload.document).first():
        raise HTTPException(409, "Documento ya registrado.")
    e = Employee(**payload.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.put("/employees/{employee_id}", response_model=EmployeePublic)
def update_employee(employee_id: int, payload: EmployeeUpsert,
                    _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(404, "Empleado no encontrado.")
    for f, v in payload.model_dump().items():
        setattr(e, f, v)
    db.commit()
    db.refresh(e)
    return e


@router.delete("/employees/{employee_id}", response_model=ApiMessage)
def archive_employee(employee_id: int, _: dict = Depends(require_admin),
                     db: Session = Depends(get_db)):
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(404, "Empleado no encontrado.")
    e.employment_status = "inactive"
    db.commit()
    return ApiMessage(message="Empleado marcado como inactivo.")


# -----------------------------------------------------------------------------
# Gastos
# -----------------------------------------------------------------------------


@router.get("/expenses", response_model=list[ExpensePublic])
def list_expenses(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(Expense).order_by(Expense.expense_date.desc()).limit(500).all()


@router.post("/expenses", response_model=ExpensePublic, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseUpsert, admin_id: int = Depends(current_user_id),
                   _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    e = Expense(**payload.model_dump(), created_by=admin_id)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.delete("/expenses/{expense_id}", response_model=ApiMessage)
def delete_expense(expense_id: int, _: dict = Depends(require_admin),
                   db: Session = Depends(get_db)):
    e = db.query(Expense).filter(Expense.id == expense_id).first()
    if not e:
        raise HTTPException(404, "Gasto no encontrado.")
    db.delete(e)
    db.commit()
    return ApiMessage(message="Gasto eliminado.")


# -----------------------------------------------------------------------------
# Finanzas: resumen de periodo
# -----------------------------------------------------------------------------


@router.get("/finance/summary", response_model=FinanceSummary)
def finance_summary(
    period_from: date | None = Query(default=None),
    period_to: date | None = Query(default=None),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Calcula ventas brutas (orders en estado PAID/ENVIADO/ENTREGADO + sum total),
    cantidad de pedidos, gastos operativos y nomina activa.
    """
    sales_q = db.query(func.coalesce(func.sum(Order.total), 0), func.count(Order.id)).filter(
        Order.status.in_(["PAID", "EN_PREPARACION", "ENVIADO", "ENTREGADO"])
    )
    expenses_q = db.query(func.coalesce(func.sum(Expense.amount), 0))
    if period_from:
        sales_q = sales_q.filter(Order.created_at >= datetime.combine(period_from, datetime.min.time()))
        expenses_q = expenses_q.filter(Expense.expense_date >= period_from)
    if period_to:
        sales_q = sales_q.filter(Order.created_at <= datetime.combine(period_to, datetime.max.time()))
        expenses_q = expenses_q.filter(Expense.expense_date <= period_to)
    gross_sales, orders_count = sales_q.first()
    operating_expenses = expenses_q.scalar() or 0
    payroll = (
        db.query(func.coalesce(func.sum(Employee.salary), 0))
        .filter(Employee.employment_status == "active")
        .scalar() or 0
    )
    net = float(gross_sales) - float(operating_expenses) - float(payroll)
    return FinanceSummary(
        period_from=period_from, period_to=period_to,
        gross_sales=float(gross_sales), orders_count=int(orders_count or 0),
        operating_expenses=float(operating_expenses), payroll=float(payroll),
        net_profit=net,
    )


# -----------------------------------------------------------------------------
# Resenas (admin)
# -----------------------------------------------------------------------------


@router.get("/reviews", response_model=list[ReviewPublic])
def admin_list_reviews(
    only_pending: bool = False,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Review)
    if only_pending:
        q = q.filter(Review.approved.is_(False))
    return q.order_by(Review.id.desc()).limit(500).all()


@router.patch("/reviews/{review_id}/approve", response_model=ApiMessage)
def approve_review(review_id: int, _: dict = Depends(require_admin),
                   db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(404, "Resena no encontrada.")
    r.approved = True
    db.commit()
    return ApiMessage(message="Resena aprobada.")


@router.delete("/reviews/{review_id}", response_model=ApiMessage)
def delete_review(review_id: int, _: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(404, "Resena no encontrada.")
    db.delete(r)
    db.commit()
    return ApiMessage(message="Resena eliminada.")


# -----------------------------------------------------------------------------
# Audit logs
# -----------------------------------------------------------------------------


@router.get("/audit-logs", response_model=list[OrderAuditLogPublic])
def list_audit_logs(
    order_id: int | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(OrderAuditLog)
    if order_id:
        q = q.filter(OrderAuditLog.order_id == order_id)
    return q.order_by(OrderAuditLog.id.desc()).limit(limit).all()
