# backend_legacy_monolito - referencia historica

Este directorio contiene el backend FastAPI original de la Fase 1 del proyecto
(monolito mono-proceso). Se preserva como referencia historica y para evidenciar
el punto de partida de la migracion a microservicios realizada en Fase 2.

> **No se levanta con `docker compose up`.** La arquitectura viva del proyecto
> son los 5 microservicios en `services/`. Este directorio queda fuera del
> flujo normal de ejecucion.

## Para correrlo aisladamente (si se necesita comparar comportamiento)

```powershell
cd backend_legacy_monolito
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --port 8000
```

Apunta al esquema `tienda_digital` del MySQL que levanta `docker-compose.yml`
(coexiste con los 5 esquemas de los microservicios).

API local: <http://localhost:8000>.

## Que tiene

Este monolito implementa los mismos RF-01 a RF-09 que los microservicios, pero
todo en un solo proceso FastAPI con una sola base de datos. La estructura es:

- `main.py` - entry point
- `app/api/` - routers por dominio (auth, catalog, cart, orders, admin, ...)
- `app/core/` - configuracion, db, seguridad
- `app/models/entities.py` - todas las entidades SQLAlchemy en un archivo
- `app/schemas/` - contratos Pydantic
- `app/services/` - logica de negocio y auditoria

## Relacion con la arquitectura viva

| Dominio del monolito | Microservicio equivalente |
|---|---|
| `app/api/auth.py` + `app/core/security.py` | `services/auth-service/` |
| `app/api/catalog.py` | `services/catalog-service/` |
| inventario (en `app/api/catalog.py` + `entities.py`) | `services/inventory-service/` |
| `app/api/cart.py` + `app/api/orders.py` | `services/commerce-service/` (con SAGA) |
| pago simulado (en `app/api/orders.py`) | `services/payment-service/` (con Circuit Breaker) |

La trazabilidad completa de la migracion esta en `docs/fase2.md`.

## Eliminacion

Si en el futuro se decide retirar definitivamente el monolito, puede borrarse
este directorio sin afectar la arquitectura microservicios:

```powershell
git rm -r backend_legacy_monolito
```

Y eliminar la nota de la seccion final del README.md principal.
