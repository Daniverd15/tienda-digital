# Arquitectura

## Vista general

```mermaid
flowchart LR
  UI[React + Vite<br/>:5173] -->|HTTPS/JSON + JWT| GW[API Gateway<br/>Nginx :80]

  GW -->|/api/auth, /api/users<br/>/api/admin/customers| AUTH[Auth Service<br/>:8001]
  GW -->|/api/products, /api/catalog<br/>/api/admin/products| CAT[Catalog Service<br/>:8002]
  GW -->|/api/inventory, /api/variants<br/>/api/admin/inventory| INV[Inventory Service<br/>:8003]
  GW -->|/api/cart, /api/checkout<br/>/api/orders, /api/reviews| COM[Commerce Service<br/>:8004]
  GW -->|/api/payments<br/>/api/payments/circuit| PAY[Payment Service<br/>:8005]

  AUTH --> DB_A[(auth_db)]
  CAT  --> DB_C[(catalog_db)]
  INV  --> DB_I[(inventory_db)]
  COM  --> DB_O[(commerce_db)]
  PAY  --> DB_P[(payments_db)]

  CAT  -.cache-aside.-> R[(Redis)]
  INV  -.lock distribuido.-> R
  PAY  -.circuit breaker.-> R

  COM -->|SAGA: reserve| INV
  COM -->|SAGA: charge|  PAY
  COM -->|SAGA: confirm/release| INV
  PAY  -->|charge HTTP| MOCK[Payment Mock<br/>:9000]

  AUTH -->|SMTP| MH[Mailhog :1025]
  COM  -->|SMTP| MH

  DB_A === MYSQL[(MySQL 8.4<br/>multi-schema)]
  DB_C === MYSQL
  DB_I === MYSQL
  DB_O === MYSQL
  DB_P === MYSQL
```

El frontend consume el API Gateway como unico punto de entrada. El gateway aplica
routing por path, headers de seguridad, CORS, rate limit en `/api/auth/login` y
propaga `X-Correlation-Id` a cada microservicio. Cada microservicio valida JWT
localmente con un secreto HS256 compartido (SSO sin llamadas de vuelta al Auth).

## Bounded contexts y servicios

| Servicio | Dominio | Datos propios | Patrones de resiliencia |
|---|---|---|---|
| Auth | Identidad, sesiones, perfil, bitacora de accesos | `auth_db` | Rate limit en login, JWT con refresh y revocacion |
| Catalog | Catalogo, categorias, tienda, mensajes, rating agregado | `catalog_db` | Cache-Aside (TTL 60-300s) + degradacion si Redis falla |
| Inventory | Variantes, reservas, confirmaciones, movimientos, alertas | `inventory_db` | Lock distribuido Redis + SELECT FOR UPDATE + scheduler de expiracion |
| Commerce | Carrito, checkout, pedidos, resenas, notificaciones, finanzas | `commerce_db` | Orquestador SAGA sincrona REST + compensaciones HTTP + idempotencia |
| Payment | Cobros contra pasarela, refunds, reconciliacion | `payments_db` | Circuit Breaker (Redis) + reintentos exponenciales + worker reconciler async |

## Separacion logica del repositorio

- `frontend/src/` - SPA React con paginas, componentes, contexto, cliente API
- `services/<svc>-service/app/` - cada microservicio FastAPI con la misma estructura:
  - `api/` - routers REST (publicos + admin + internos)
  - `core/` - configuracion, db, seguridad, cache, lock, circuit breaker
  - `models/` - entidades SQLAlchemy
  - `schemas/` - contratos Pydantic
  - `services/` - logica de negocio y orquestadores
- `api-gateway/conf.d/gateway.conf` - rutas Nginx y headers
- `database-init/` - scripts de creacion de esquemas + GRANT por servicio
- `payment-mock/` - simulador de la pasarela
- `scripts/{e2e,chaos}/` - smoke E2E + experimentos del Simian Army
- `database/` - schema y seed del monolito (mismo MySQL, esquema `tienda_digital`)
- `backend_legacy_monolito/` - monolito Fase 1 preservado como referencia historica
- `docs/` - documentacion del proyecto

## Patrones arquitecturales aplicados

| Patron | Donde | Detalle |
|---|---|---|
| **API Gateway** | Nginx :80 | Routing por path, headers de seguridad, CORS, rate limit, correlation-id |
| **SSO con JWT compartido** | Auth + secret HS256 | Cada servicio valida sin llamar a Auth |
| **Database per Service** | MySQL multi-schema | 5 esquemas + `GRANT` exclusivo por usuario; aislamiento real validado por Conformity Monkey |
| **Cache-Aside** | Catalog + Redis | TTL 60-300s, invalidacion al editar, degradacion graceful si Redis falla |
| **Lock distribuido** | Inventory + Redis | `SET NX EX` + script Lua `release-by-token` para evitar condiciones de carrera |
| **SAGA orquestada sincrona** | Commerce | `reserve -> charge -> confirm | release` con compensaciones HTTP en el mismo flujo |
| **Circuit Breaker** | Payment + Redis | CLOSED/OPEN/HALF_OPEN, threshold=5, open_ttl=60s. Rechazo en <100ms cuando OPEN |
| **Retry con backoff exponencial** | Payment -> Mock | 250ms / 500ms / 1s en errores transitorios; distingue REJECTED (negocio) de 5xx (infra) |
| **Worker reconciler** | Payment | Async, cada 5 min reintenta PENDING/FAILED |
| **Idempotencia** | Commerce checkout | Header `Idempotency-Key` |
| **Healthchecks unificados** | Gateway + cada servicio | `/health/<svc>` consolidados para Doctor Monkey |
| **Bitacora con correlation-id** | Todos | Gateway inyecta y los servicios lo propagan a logs |

## Decisiones de migracion

- **MVP 5 servicios** (Auth, Catalog, Inventory, Commerce, Payment) por encima del
  planteamiento inicial de 11 microservicios, para mantener el alcance ejecutable
  en un curso academico.
- **Database per Service en variante logica:** una sola instancia MySQL con 5
  esquemas separados y un usuario por servicio con `GRANT` exclusivo. Permite
  Conformity Monkey real (los usuarios no pueden cruzar esquema) sin pagar el
  costo operativo de 5 instancias.
- **SAGA orquestada sincrona REST** como punto de partida (Nivel 1 de alcance).
  La coreografia AMQP queda como evolucion (Nivel 3).
- **Pago simulado** con pasarela mock local con 4 escenarios (APPROVED, REJECTED,
  PENDING, FAILED) controlados por el monto.
- **Coexistencia con el monolito legacy:** el directorio `backend_legacy_monolito/`
  apunta al esquema historico `tienda_digital` y no se levanta en el compose. Se
  preserva como evidencia del punto de partida.

## Preparacion para produccion

- Variables por `.env` y por servicio, sin secretos en codigo
- CORS configurable en el gateway
- `JWT_SECRET` externo y rotable
- Headers de seguridad (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)
- Docker Compose local; cada servicio puede contenedorizarse y desplegarse
  independientemente (12-factor) sin cambiar contratos
- Healthchecks compatibles con orquestadores (Kubernetes/ECS)

## Trazabilidad con el informe Fase 1

- Seccion 3.2.3 - Database per Service: implementado en `database-init/`
- Seccion 11.0 - SAGA orquestada sincrona: implementado en
  `services/commerce-service/app/services/checkout_saga.py`
- Seccion 12.0 - Circuit Breaker + reintentos: implementado en
  `services/payment-service/app/core/circuit_breaker.py` y `services/payment-service/app/services/gateway_client.py`
- Seccion 18 - Chaos Engineering / Simian Army: 5 scripts en `scripts/{e2e,chaos}/`
- Seccion 19.0 - Niveles de alcance: Nivel 1 + parte de Nivel 2 implementados
