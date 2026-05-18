# Tienda Digital - Arquitectura de Microservicios

Aplicacion academica de tienda digital. Inicialmente un monolito FastAPI (Fase 1
del curso de Ingenieria de Software), migrada en Fase 2 a una arquitectura de
microservicios con 5 servicios independientes mas API Gateway, MySQL multi-schema,
Redis, SMTP local y pasarela de pago mock.

> **Estado del proyecto:** Fase 2 completada. Los 9 bloques de migracion estan
> DONE y validados con 133 / 133 verificaciones automatizadas (5 scripts:
> 1 E2E completo + 4 experimentos de Chaos Engineering). Detalle en
> [`docs/fase2.md`](docs/fase2.md).

## Mapa de servicios

| Servicio | Puerto | Responsabilidad principal | Patrones aplicados |
|---|---|---|---|
| API Gateway (Nginx) | 80 | Routing por path `/api/<svc>` y healthcheck unificado | Reverse proxy, single entry-point |
| Auth Service | 8001 | Registro, login, refresh, logout, JWT HS256, bitacora de accesos | SSO con JWT compartido, password policy |
| Catalog Service | 8002 | Productos, categorias, tienda, mensajes, resena agregada | Cache-Aside (Redis, TTL 60-300s) |
| Inventory Service | 8003 | Variantes, stock, reservas, confirmaciones, movimientos | Lock distribuido Redis + SELECT FOR UPDATE, scheduler de expiracion |
| Commerce Service | 8004 | Carrito, checkout, pedidos, resenas, notificaciones, admin/finanzas | SAGA orquestada sincrona, compensaciones HTTP |
| Payment Service | 8005 | Cobros contra pasarela mock, reconciliacion, refunds | Circuit Breaker, reintentos exponenciales, worker reconciler |
| Payment Mock | 9000 | Pasarela de prueba (APPROVED/REJECTED/PENDING/FAILED) | Simulador local |
| MySQL 8.4 | 3306 | 5 esquemas aislados + monolito legacy preservado | Database per Service (logica) |
| phpMyAdmin | 8080 | UI de inspeccion de los esquemas | - |
| Redis 7 | 6379 | Cache, locks distribuidos, contadores del CB | - |
| Mailhog SMTP | 1025 / 8025 | Buzon local para correos transaccionales | - |

Cada microservicio tiene su propio esquema MySQL y un usuario con `GRANT` exclusivo
sobre ese esquema (`auth_db`, `catalog_db`, `inventory_db`, `commerce_db`,
`payments_db`). El esquema `tienda_digital` del monolito legacy se conserva como
referencia historica.

## Requisitos previos

- Docker Desktop con Docker Compose v2
- 4 GB de RAM libres (12 contenedores ligeros)
- Puertos libres: 80, 1025, 3306, 6379, 8001-8005, 8025, 8080, 9000
- (Opcional) Node.js 20+ para el frontend React fuera de Docker

## Levantar todo

```powershell
# Construir e iniciar (12 contenedores en total)
docker compose up --build -d

# Verificar
docker compose ps

# Healthcheck a traves del gateway
curl http://localhost/health/gateway
curl http://localhost/health/auth
curl http://localhost/health/catalog
curl http://localhost/health/inventory
curl http://localhost/health/commerce
curl http://localhost/health/payment
```

Los 6 healthchecks deben responder `{"status":"ok",...}`. El primer arranque
tarda ~30s porque MySQL ejecuta `schema.sql`, `seed.sql`, crea esquemas y
otorga GRANT por servicio.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

App: <http://localhost:5173>. El cliente Axios apunta a `http://localhost/api`
(API Gateway).

## Credenciales seed

| Rol | Email | Password |
|---|---|---|
| Admin | `admin@tienda.com` | `Admin1234*` |

Los clientes se crean por `POST /api/auth/register`. Las contrasenas usan
bcrypt (`passlib[bcrypt]==1.7.4` + `bcrypt==4.0.1`) y deben cumplir politica
fuerte (>=8, mayusculas, minusculas, digito, simbolo).

## Smoke test manual

```powershell
# Login admin
curl -X POST http://localhost/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{"email":"admin@tienda.com","password":"Admin1234*"}'

# Catalogo publico (Cache-Aside activo, TTL 60s)
curl http://localhost/api/products

# Estado del Circuit Breaker (requiere admin token)
curl http://localhost/api/payments/circuit/state -H "Authorization: Bearer <token>"
```

Mailhog UI: <http://localhost:8025> (verifica correos de bienvenida y de
transicion de pedidos).

## Pruebas automatizadas (E2E + Chaos Engineering)

Cinco scripts ejecutables validan 133 hipotesis arquitecturales:

```bash
bash scripts/e2e/flujo_completo.sh             # 34 PASS - flujo completo cruza los 5 servicios
bash scripts/chaos/conformity_monkey.sh        # 51 PASS - Database per Service aislamiento real
bash scripts/chaos/security_monkey.sh          # 27 PASS - 401/403, rate limit, no leaks
bash scripts/chaos/chaos_monkey_inventory.sh   # 12 PASS - tira Inventory; degradacion grace
bash scripts/chaos/latency_monkey_payment.sh   #  9 PASS - abre CB con 5 fallos
```

Detalle, hipotesis y trazabilidad con el informe en
[`docs/chaos.md`](docs/chaos.md).

## Documentacion

- [`docs/fase2.md`](docs/fase2.md) - Bitacora de los 9 bloques de migracion
- [`docs/endpoints.md`](docs/endpoints.md) - Endpoints consolidados de los 5 microservicios
- [`docs/arquitectura.md`](docs/arquitectura.md) - Diagrama + decisiones tecnicas
- [`docs/chaos.md`](docs/chaos.md) - Runbook de Chaos Engineering
- [`docs/instalacion.md`](docs/instalacion.md) - Instalacion paso a paso
- [`docs/pruebas.md`](docs/pruebas.md) - Estrategia de pruebas
- [`docs/backlog-commits.md`](docs/backlog-commits.md) - Trazabilidad RF/RNF con commits

## Estructura del repositorio

```
tienda-digital/
  api-gateway/                Nginx + conf.d/gateway.conf
  services/
    auth-service/             FastAPI 8001 (SSO + JWT)
    catalog-service/          FastAPI 8002 (Cache-Aside)
    inventory-service/        FastAPI 8003 (lock + scheduler)
    commerce-service/         FastAPI 8004 (SAGA orquestada)
    payment-service/          FastAPI 8005 (Circuit Breaker)
  payment-mock/               Pasarela de prueba puerto 9000
  database-init/              Scripts de creacion de esquemas + GRANT por servicio
  database/                   Schema y seed historicos del monolito
  scripts/
    e2e/flujo_completo.sh     Smoke E2E (34 verificaciones)
    chaos/                    4 experimentos del Simian Army (99 verificaciones)
  frontend/                   React + Vite (apunta al gateway)
  backend_legacy_monolito/    Monolito Fase 1 (preservado como referencia, no se levanta)
  docs/                       Documentacion del proyecto
  docker-compose.yml          12 contenedores: 5 servicios + gateway + infra + mock
```

## Detener / limpiar

```powershell
docker compose down               # Detiene y elimina contenedores (preserva volumen MySQL)
docker compose down -v            # ATENCION: tambien borra el volumen mysql_data
```

## Integrantes y roles

- **Daniel Villamizar** (`dvillamizar435@unab.edu.co`) - Frontend (React, Vite, migracion al gateway).
- **Santiago Perez** (`santivivivi@gmail.com`) - Backend (5 microservicios, SAGA, Circuit Breaker, Cache-Aside, locks).
- **Tomas Urieles** (`tomasurieles31@gmail.com`) - Scrum Master, infraestructura (Docker Compose, gateway, scripts de chaos, documentacion).

## Requisitos cubiertos

Se implementan RF-01 a RF-09 y RNF-01 a RNF-03 del SRS original, ahora distribuidos
entre los 5 microservicios. La trazabilidad detallada esta en
[`docs/backlog-commits.md`](docs/backlog-commits.md).

## Nota sobre el monolito legacy

El backend original FastAPI mono-proceso se preserva en
`backend_legacy_monolito/` como referencia historica. No se levanta con
`docker compose up`. Para correrlo aisladamente:

```powershell
cd backend_legacy_monolito
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --port 8000
```

Apunta al esquema `tienda_digital` (el mismo MySQL del compose). La arquitectura
viva del proyecto son los microservicios; el monolito queda como evidencia del
punto de partida de la Fase 2.
