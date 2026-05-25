# Informe Técnico — Fase 2: Migración a Arquitectura de Microservicios
## Tienda Digital — Curso de Arquitectura de Software — UNAB

---

## 1. Introducción

Este informe documenta la implementación de la Fase 2 del proyecto Tienda Digital, correspondiente a la migración del monolito FastAPI (Fase 1) a una arquitectura de microservicios desplegable localmente mediante Docker Compose.

La arquitectura implementada materializa los patrones y decisiones de diseño planteados en el informe de Fase 1. El sistema resultante es completamente funcional, ejecutable con un solo comando (`docker compose up --build -d`) y validado con 133 verificaciones automatizadas distribuidas en cinco scripts ejecutables.

**Equipo de trabajo:**
- Daniel Villamizar (`dvillamizar435@unab.edu.co`) — Frontend React + Vite, migración al gateway
- Santiago Pérez (`santivivivi@gmail.com`) — Backend: 5 microservicios, SAGA, Circuit Breaker, Cache-Aside, locks distribuidos
- Tomás Urieles (`tomasurieles31@gmail.com`) — Infraestructura Docker Compose, gateway Nginx, scripts de chaos, documentación

---

## 2. Arquitectura General

### 2.1 Diagrama de servicios

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              Cliente (navegador)                               │
│                         React + Vite  :5173                                    │
└─────────────────────────────────┬──────────────────────────────────────────────┘
                                  │ HTTP + JWT Bearer
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         API Gateway — Nginx :80                                 │
│  Routing por path • CORS • Security headers • Rate limit /auth/login           │
│  Correlación ID (X-Correlation-Id) • Healthchecks unificados                  │
└──────┬──────────┬──────────┬───────────────┬──────────────────┬────────────────┘
       │          │          │               │                  │
  /api/auth  /api/catalog /api/inventory /api/cart,checkout /api/payments
  /api/users /api/products /api/variants  /api/orders        /api/payments/circuit
  /api/admin /api/store                   /api/reviews
       │          │          │               │                  │
       ▼          ▼          ▼               ▼                  ▼
  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────┐       ┌──────────┐
  │  Auth   │ │ Catalog │ │Inventory│ │ Commerce │       │ Payment  │
  │  :8001  │ │  :8002  │ │  :8003  │ │  :8004   │       │  :8005   │
  │FastAPI  │ │FastAPI  │ │FastAPI  │ │ FastAPI  │       │ FastAPI  │
  └────┬────┘ └────┬────┘ └────┬────┘ └────┬─────┘       └────┬─────┘
       │           │           │            │                   │
       ▼           ▼           ▼       SAGA REST           Circuit Breaker
  auth_db     catalog_db  inventory_db ┌───┴────┐         ┌────┴─────┐
                                       │reserve │         │  charge  │
                          ┌────────────┤confirm │         │          │
                          │  Redis 7   │release ├─────────►  Mock    │
                          │Cache-Aside │        │         │  :9000   │
                          │Lock dist.  └────────┘         └──────────┘
                          │CB counters commerce_db    payments_db
                          └──────────────────────────────────────────┘

Infra: MySQL 8.4 (5 schemas) · Redis 7 · Mailhog :1025/:8025 · phpMyAdmin :8080
       Payment Mock :9000
```

### 2.2 Mapa de contenedores

| Contenedor | Imagen/Build | Puerto | Responsabilidad |
|---|---|---|---|
| `tienda_gateway` | nginx:1.27-alpine | 80 | Proxy inverso, routing, seguridad |
| `tienda_auth` | build ./services/auth-service | 8001 | Identidad, JWT, bitácora |
| `tienda_catalog` | build ./services/catalog-service | 8002 | Catálogo, Cache-Aside Redis |
| `tienda_inventory` | build ./services/inventory-service | 8003 | Stock, reservas, lock distribuido |
| `tienda_commerce` | build ./services/commerce-service | 8004 | Carrito, SAGA, pedidos, reseñas |
| `tienda_payment` | build ./services/payment-service | 8005 | Cobros, Circuit Breaker |
| `tienda_payment_mock` | build ./payment-mock | 9000 | Simulador de pasarela |
| `tienda_digital_mysql` | mysql:8.4 | 3306 | 5 schemas aislados + legacy |
| `tienda_redis` | redis:7-alpine | 6379 | Cache, locks, CB counters |
| `tienda_mailhog` | mailhog/mailhog | 1025/8025 | SMTP local |
| `tienda_phpmyadmin` | phpmyadmin | 8080 | Inspección de schemas |
| **Total: 11 contenedores de servicio** | | | |

### 2.3 Red Docker

Todos los contenedores se comunican en la red bridge `tienda_net`. Los servicios de negocio se llaman entre sí por nombre de contenedor (DNS interno de Docker), nunca por IP. El único punto de entrada externo es el gateway en el puerto 80.

---

## 3. Servicios Implementados y Endpoints

### 3.1 Auth Service (puerto 8001)

**Responsabilidad:** Gestión de identidad. Emite pares de tokens JWT HS256 (access 60 min + refresh 7 días). Cada servicio valida el access token localmente con el secreto compartido — no hay llamadas de vuelta al Auth Service (SSO verdadero).

| Método | Endpoint gateway | Descripción | Auth |
|---|---|---|---|
| POST | `/api/auth/register` | Crear cuenta cliente. Valida fortaleza de contraseña. Envía correo bienvenida vía Mailhog. | Público |
| POST | `/api/auth/login` | Login. Rate limit 5 req/min/IP en gateway. Registra evento en bitácora. | Público |
| POST | `/api/auth/refresh` | Rota el refresh token (revoca viejo, emite nuevo par). | Bearer refresh |
| POST | `/api/auth/logout` | Revoca todos los refresh tokens activos del usuario. | Bearer |
| GET | `/api/auth/me` | Perfil del usuario autenticado. | Bearer |
| GET | `/api/users/me` | Perfil completo. | Bearer |
| PUT | `/api/users/me` | Actualizar perfil. | Bearer |
| GET | `/api/admin/customers` | Lista de clientes registrados. | Admin |
| GET | `/api/admin/customers/{id}` | Detalle de cliente. | Admin |
| GET | `/api/admin/access-logs` | Bitácora de login/register/refresh/logout con IP, UA, correlation_id. | Admin |
| GET | `/health/auth` | Healthcheck (MySQL conectado). | Público |

**Credencial seed:** `admin@tienda.com` / `Admin1234*`

**Política de contraseña:** ≥8 caracteres, al menos 1 mayúscula, 1 minúscula, 1 dígito, 1 símbolo.

**Modelo de tokens:** access_token (stateless, no almacenado), refresh_token (hash SHA-256 almacenado en `auth_db.refresh_tokens`, revocable por logout o por uso único).

---

### 3.2 Catalog Service (puerto 8002)

**Responsabilidad:** Catálogo de productos, categorías, configuración de tienda, mensajes informativos y rating agregado. Implementa Cache-Aside con Redis.

**Cache-Aside implementado:** todos los `GET` públicos consultan Redis antes de MySQL. TTL: productos=300s, categorías=180s, overview=60s. Invalidación al editar mediante borrado de prefijo. Degradación graceful: si Redis cae, sirve desde MySQL sin error.

| Método | Endpoint | Auth |
|---|---|---|
| GET | `/api/catalog` | Público |
| GET | `/api/products` (soporta `?q=&category_id=`) | Público |
| GET | `/api/products/{id}` (enriquece con variantes de Inventory) | Público |
| GET | `/api/categories` | Público |
| GET | `/api/store/settings` | Público |
| GET | `/api/store/messages` | Público |
| GET/POST | `/api/admin/products` | Admin |
| PUT/DELETE | `/api/admin/products/{id}` | Admin |
| POST | `/api/admin/products/{id}/images` | Admin |
| GET/POST | `/api/admin/categories` | Admin |
| GET/PUT | `/api/admin/store/settings` | Admin |
| GET/POST | `/api/admin/messages` | Admin |
| GET | `/health/catalog` | Público |

**Seed:** 3 categorías (Ropa urbana, Calzado, Accesorios) + 5 productos activos.

---

### 3.3 Inventory Service (puerto 8003)

**Responsabilidad:** Stock de variantes (SKU/talla/color), reservas atómicas y confirmaciones. Implementa lock distribuido Redis + SELECT FOR UPDATE. Scheduler interno expira reservas vencidas cada 60 segundos.

**Lock distribuido:** `SET NX EX <ttl> <token>` adquiere el lock por variante. Script Lua de release verifica el token antes de liberar (evita liberar el lock de otro proceso). Fallback: `SELECT FOR UPDATE` en MySQL si Redis no está disponible.

| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| GET | `/api/inventory/products/{product_id}/variants` | Variantes activas | Público |
| GET | `/api/inventory/variants/{variant_id}` | Detalle de variante | Público |
| POST | `/api/inventory/reserve` | Reserva atómica (SAGA paso 1) | Internal |
| POST | `/api/inventory/confirm/{order_id}` | Confirma reserva, descuenta stock (SAGA paso 3) | Internal |
| POST | `/api/inventory/release` | Libera reserva (compensación SAGA) | Internal |
| GET/POST | `/api/admin/variants` | CRUD de variantes | Admin |
| GET/POST | `/api/admin/inventory/movements` | Movimientos manuales | Admin |
| GET | `/api/admin/inventory/alerts` | Alertas de stock mínimo | Admin |
| POST | `/api/admin/inventory/expire-pending` | Forzar expiración de reservas | Admin |
| GET | `/health/inventory` | Healthcheck | Público |

**Seed:** 11 variantes para los 5 productos (tallas S/M/L, colores, stock inicial).

---

### 3.4 Commerce Service (puerto 8004)

**Responsabilidad:** Carrito, checkout con SAGA orquestada, pedidos, reseñas, notificaciones in-app, finanzas admin. Es el **orquestador de la SAGA**.

**SAGA orquestada sincrona** (ver sección 5.2 para detalle completo):
```
POST /checkout  →  1. POST /inventory/reserve
                   2. POST /payments (charge)
                →  3a. POST /inventory/confirm  (si APPROVED → Order PAID)
                →  3b. POST /inventory/release  (si REJECTED/ERROR → compensación)
```

| Método | Endpoint | Auth |
|---|---|---|
| GET | `/api/cart` | Cliente |
| POST | `/api/cart/items` | Cliente |
| PUT | `/api/cart/items/{id}` | Cliente |
| DELETE | `/api/cart/items/{id}` | Cliente |
| DELETE | `/api/cart` | Cliente |
| POST | `/api/checkout` (Idempotency-Key requerido) | Cliente |
| GET | `/api/orders/mine` | Cliente |
| GET | `/api/orders/{id}` | Cliente |
| POST | `/api/reviews` | Cliente (requiere Order ENTREGADO) |
| GET | `/api/reviews/product/{id}` | Público |
| GET | `/api/notifications` | Cliente |
| PATCH | `/api/notifications/{id}/read` | Cliente |
| GET | `/api/admin/orders` | Admin |
| PATCH | `/api/admin/orders/{id}/status` | Admin |
| GET | `/api/admin/finance/summary` | Admin |
| GET/POST | `/api/admin/employees` | Admin |
| GET/POST | `/api/admin/expenses` | Admin |
| PATCH | `/api/admin/reviews/{id}/approve` | Admin |
| GET | `/health/commerce` | Público |

---

### 3.5 Payment Service (puerto 8005)

**Responsabilidad:** Cobros contra la pasarela mock. Implementa Circuit Breaker Redis (CLOSED→OPEN→HALF_OPEN), reintentos con backoff exponencial y worker de reconciliación async.

| Método | Endpoint | Descripción | Auth |
|---|---|---|---|
| POST | `/api/payments` | Charge. Pasa por CB. Body: `{"order_id":"...", "amount": float}` | Cliente/Admin |
| GET | `/api/payments/{id}` | Detalle de pago | Cliente/Admin |
| GET | `/api/payments/circuit/state` | Estado del CB (state, failures, TTL restante) | Admin |
| POST | `/api/payments/circuit/reset` | Reset manual del CB | Admin |
| POST | `/api/payments/{id}/reconcile` | Forzar reconciliación de pago | Admin |
| POST | `/api/payments/refund` | Refund | Admin |
| GET | `/health/payment` | Healthcheck | Público |

**Pasarela mock** — respuestas deterministas según los centavos del monto:
| Centavos | Resultado | HTTP |
|---|---|---|
| `.00` | APPROVED | 200 |
| `.77` | REJECTED | 200 |
| `.99` | PENDING | 200 |
| `.88` | Crash 500 (error de infraestructura) | 500 |

---

## 4. Patrones Arquitecturales Implementados

### 4.1 API Gateway (Nginx)

**Implementación:** `api-gateway/conf.d/gateway.conf`

El gateway aplica:
- **Routing por path prefix:** `/api/auth` → `upstream auth_upstream` (puerto 8001), etc.
- **Rewrites:** elimina el prefijo `/api/<svc>` antes de hacer proxy al microservicio
- **Headers de seguridad:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`
- **CORS:** preflight OPTIONS respondido directamente por el gateway
- **Rate limiting:** zona `auth_limit` — 5 req/min/IP en `/api/auth/login`
- **Correlation ID:** genera `$request_id` (UUID) si no viene en el request; lo propaga como `X-Correlation-Id` al microservicio y lo incluye en el log

**Evidencia de conformidad:** Security Monkey verifica los 3 headers en 27 assertions (27 PASS).

---

### 4.2 Database per Service

**Implementación:** `database-init/01_create_databases.sql` + `02_create_users.sql`

Cada microservicio tiene su propio schema MySQL y un usuario con `GRANT` exclusivo sobre ese schema. Ningún usuario puede acceder al schema de otro servicio.

```sql
-- Ejemplo de aislamiento real (02_create_users.sql):
CREATE USER 'auth_user'@'%' IDENTIFIED BY 'auth_pass';
GRANT ALL PRIVILEGES ON auth_db.* TO 'auth_user'@'%';
-- auth_user NO tiene acceso a catalog_db, inventory_db, etc.
```

**Evidencia de conformidad:** Conformity Monkey ejecuta 51 assertions verificando el aislamiento real con credenciales cruzadas.

---

### 4.3 SSO con JWT HS256 Compartido

**Implementación:** `services/*/app/core/security.py` (idéntico en los 5 servicios)

Cada servicio valida el token localmente usando el `JWT_SECRET` compartido (inyectado como variable de entorno en `docker-compose.yml`). El payload del access token incluye `sub` (user_id), `role` y `email`, suficientes para autorizar sin hacer llamadas al Auth Service.

```python
# En cualquier servicio:
payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
user_id = int(payload["sub"])
role = payload["role"]  # "customer" o "admin"
```

El refresh token tiene `type="refresh"` en el payload y se almacena hasheado (SHA-256) en `auth_db.refresh_tokens`. Los access tokens son stateless y no se almacenan.

---

### 4.4 Cache-Aside (Catalog Service)

**Implementación:** `services/catalog-service/app/core/cache.py`

```python
# Flujo Cache-Aside:
cached = redis_client.get(cache_key)
if cached:
    return json.loads(cached)           # HIT: serve from Redis

data = db.query(Product).filter(...).all()   # MISS: query MySQL
redis_client.setex(cache_key, ttl, json.dumps(data))   # fill cache
return data
```

TTL: productos individuales 300s, lista de productos 180s, overview 60s. Invalidación: al editar un producto, se borran todas las claves con el prefijo `catalog:products:*`.

**Degradación graceful:** si Redis no responde, la excepción se captura y el servicio sirve desde MySQL sin error. El cliente no percibe la diferencia.

---

### 4.5 Distributed Lock (Inventory Service)

**Implementación:** `services/inventory-service/app/core/redis_lock.py`

```python
# Adquirir lock:
token = secrets.token_hex(16)
acquired = redis.set(f"lock:{resource}", token, nx=True, ex=ttl_seconds)

# Liberar lock (script Lua — atómico):
LUA_RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""
redis.eval(LUA_RELEASE, 1, lock_key, token)
```

El script Lua garantiza que solo el proceso que adquirió el lock pueda liberarlo (evita condición de carrera donde proceso A libera el lock de proceso B). Fallback: si Redis no está disponible, se usa `SELECT FOR UPDATE` en MySQL.

**Verificación de concurrencia:** Conformity Monkey valida que 2 reservas simultáneas sobre stock=4 con cantidad=3 → una pasa (201), otra falla (409). Ambas son correctas.

---

### 4.6 SAGA Orquestada Síncrona (Commerce Service)

**Implementación:** `services/commerce-service/app/services/checkout_saga.py`

La SAGA es el patrón más complejo del sistema. Commerce actúa como orquestador: coordina llamadas REST a Inventory y Payment y ejecuta compensaciones si algún paso falla.

**Flujo Happy Path:**
```
Cliente → POST /checkout
   │
   ├─ 1. POST /inventory/reserve  →  Lock Redis + SELECT FOR UPDATE
   │       ✓ 201 → reservation_ids
   │
   ├─ 2. POST /payments           →  Circuit Breaker check → POST /charge (mock)
   │       ✓ APPROVED
   │
   ├─ 3. POST /inventory/confirm  →  stock -= qty, reserva eliminada
   │
   ├─ 4. Persistir Order(PAID) + OrderItems en commerce_db
   ├─ 5. Notificación in-app + correo SMTP (Mailhog)
   ├─ 6. Cart → status = "checked_out"
   └─ 7. Devolver 201 {order_id, status:"PAID", payment_status:"APPROVED"}
```

**Flujos de compensación:**
| Escenario | Paso que falla | Compensación | HTTP al cliente |
|---|---|---|---|
| Sin stock | Paso 1 (409) | — (no se reservó nada) | 409 out_of_stock |
| Inventory caído | Paso 1 (timeout) | — | 503 inventory_unavailable |
| Pago REJECTED | Paso 2 | POST /inventory/release | 402 payment_rejected |
| CB abierto (Payment) | Paso 2 (503) | POST /inventory/release | 503 payment_unavailable |
| Payment caído | Paso 2 (timeout) | POST /inventory/release | 503 payment_unavailable |

**Política MVP:** la `Order` solo se persiste si el checkout llega a `PAID`. Los intentos fallidos se registran en `FailedCheckoutAttempt` para auditoría sin contaminar el historial de pedidos.

---

### 4.7 Circuit Breaker (Payment Service)

**Implementación:** `services/payment-service/app/core/circuit_breaker.py`

**Máquina de estados:**
```
CLOSED ──(failures >= 5)──► OPEN ──(TTL 60s expira)──► HALF_OPEN
  ▲                                                          │
  └──────────────────(éxito en prueba)──────────────────────┘
                              │
                         (fallo)
                              ▼
                            OPEN
```

**Almacenamiento en Redis:**
- `cb:gateway:failures` → contador INT con TTL rolling 60s
- `cb:gateway:open` → presencia = estado OPEN; TTL = duración del open (60s)
- `cb:gateway:half_open_token` → token de prueba HALF_OPEN

**Configuración:** `failure_threshold=5`, `open_ttl_seconds=60`, `window_seconds=60`

**Comportamiento OPEN:** rechazo inmediato con HTTP 503 en <100ms sin contactar la pasarela mock, protegiendo al sistema de tiempos de espera acumulados.

**Degradación graceful:** si Redis no está disponible, el CB funciona en modo "siempre cerrado" (no protege pero tampoco bloquea el servicio).

---

### 4.8 Patrones adicionales

| Patrón | Implementación |
|---|---|
| **Healthchecks** | Docker `HEALTHCHECK` + endpoint `/health` en todos los servicios. Gateway agrega en `/health/<svc>`. |
| **Correlation ID** | Nginx genera `$request_id` y lo propaga como `X-Correlation-Id`. Cada servicio lo lee y lo incluye en logs y en tablas de auditoría. |
| **Idempotencia** | Header `Idempotency-Key` en `POST /checkout`. Si llega el mismo key dos veces, el segundo intento retorna la Order existente sin ejecutar la SAGA. |
| **Retry con backoff exponencial** | Payment service: 250ms → 500ms → 1s en errores transitorios (5xx). No aplica a REJECTED (error de negocio, no infraestructura). |
| **Worker reconciliador** | Task async en Payment corre cada 5 min y reintenta cobros en estado PENDING o FAILED. |
| **Scheduler de expiración** | Task async en Inventory corre cada 60s y libera reservas cuyo TTL de 15 min expiró. |

---

## 5. Infraestructura Docker Compose

### 5.1 Estructura del docker-compose.yml

El archivo `docker-compose.yml` define 11 servicios organizados en tres grupos:

**Grupo 1 — Persistencia e infraestructura:**
```yaml
mysql:    image mysql:8.4  # 5 schemas + legacy, healthcheck mysqladmin ping
redis:    image redis:7-alpine  # healthcheck redis-cli ping
mailhog:  image mailhog/mailhog  # SMTP :1025, UI :8025
phpmyadmin: image phpmyadmin  # inspector visual :8080
```

**Grupo 2 — API Gateway:**
```yaml
api-gateway:
  build: ./api-gateway       # nginx:1.27-alpine con gateway.conf
  ports: ["80:80"]
  depends_on:                # espera health OK de los 5 servicios
    auth-service:      { condition: service_healthy }
    catalog-service:   { condition: service_healthy }
    inventory-service: { condition: service_healthy }
    commerce-service:  { condition: service_healthy }
    payment-service:   { condition: service_healthy }
```

**Grupo 3 — Microservicios FastAPI:**
```yaml
auth-service:      build: ./services/auth-service       ports: ["8001:8001"]
catalog-service:   build: ./services/catalog-service    ports: ["8002:8002"]
inventory-service: build: ./services/inventory-service  ports: ["8003:8003"]
commerce-service:  build: ./services/commerce-service   ports: ["8004:8004"]
payment-service:   build: ./services/payment-service    ports: ["8005:8005"]
payment-mock:      build: ./payment-mock                ports: ["9000:9000"]
```

### 5.2 Variables de entorno por servicio

Cada servicio recibe su configuración por variables de entorno (nunca hardcoded en código):

```yaml
# Ejemplo auth-service:
environment:
  DATABASE_URL: mysql+pymysql://auth_user:auth_pass@mysql:3306/auth_db
  JWT_SECRET: cambiar_en_produccion_pero_compartido_entre_servicios
  SMTP_HOST: mailhog
  SMTP_PORT: 1025
```

### 5.3 Healthchecks y orden de arranque

Todos los microservicios declaran:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:800X/health').status==200 else 1)"]
  interval: 15s
  timeout: 5s
  retries: 10
  start_period: 20s
```

El gateway usa `condition: service_healthy` para todos los microservicios, garantizando que el gateway no sirve tráfico hasta que todos estén listos.

MySQL es `service_healthy` (mysqladmin ping) para los servicios que dependen de él directamente. Commerce usa `service_started` para inventory y payment porque puede manejar reintentos internos.

### 5.4 Comandos de ejecución

```powershell
# Levantar todo (primera vez: construye imágenes ~3-5 min)
docker compose up --build -d

# Verificar estado
docker compose ps

# Healthchecks a través del gateway
curl http://localhost/health/gateway
curl http://localhost/health/auth
curl http://localhost/health/catalog
curl http://localhost/health/inventory
curl http://localhost/health/commerce
curl http://localhost/health/payment

# Detener (preserva datos)
docker compose down

# Detener + borrar datos
docker compose down -v
```

---

## 6. Comparativa Fase 1 vs Fase 2

| Dimensión | Fase 1 — Monolito FastAPI | Fase 2 — Microservicios |
|---|---|---|
| **Proceso de ejecución** | 1 proceso uvicorn en puerto 8000 | 5 procesos FastAPI independientes (8001-8005) + Nginx (80) |
| **Base de datos** | 1 schema `tienda_digital` con todas las tablas | 5 schemas aislados (`auth_db`, `catalog_db`, `inventory_db`, `commerce_db`, `payments_db`) |
| **Acceso a BD** | 1 usuario MySQL con acceso total | 5 usuarios con GRANT exclusivo por schema (Database per Service) |
| **Autenticación** | JWT validado en el mismo proceso | JWT HS256 compartido, validado localmente en cada servicio (SSO sin callback) |
| **Cache** | Sin cache | Cache-Aside Redis en Catalog (TTL 60-300s) |
| **Transacciones de compra** | Transacción MySQL única | SAGA orquestada síncrona REST con compensaciones HTTP |
| **Resiliencia de pagos** | Sin protección contra fallos en cascada | Circuit Breaker Redis (CLOSED/OPEN/HALF_OPEN, threshold=5) |
| **Concurrencia de stock** | Sin control de concurrencia explícito | Lock distribuido Redis (SET NX EX) + SELECT FOR UPDATE |
| **Correo** | Simulado / no funcional | Mailhog SMTP real (captura y visualiza correos) |
| **Containerización** | Sin Docker (proceso local) | 11 contenedores Docker Compose en red `tienda_net` |
| **Pasarela de pago** | Sin pasarela | Payment Mock determinista (4 escenarios controlados por monto) |
| **Healthchecks** | Sin mecanismo formal | Docker HEALTHCHECK + endpoint `/health` por servicio |
| **Trazabilidad** | Sin correlation ID | Nginx inyecta `X-Correlation-Id`, propagado a todos los servicios y tablas de auditoría |
| **Pruebas automatizadas** | Sin suite de pruebas E2E | 133 verificaciones en 5 scripts: 1 E2E + 4 Chaos Engineering |
| **Escalabilidad** | Toda la app escala junta | Cada servicio escala independientemente |
| **Despliegue** | Requiere Python + venv local | `docker compose up --build -d` en cualquier máquina con Docker |
| **Aislamiento de fallos** | Un bug puede derribar todo | Inventory caído no afecta login ni catálogo |
| **Sección de informe Fase 1** | Base de referencia | Secciones 3.2.3, 11.0, 12.0, 13.1, 18.x → implementadas |

### 6.1 Secciones del informe Fase 1 → implementación concreta

| Sección Informe Fase 1 | Concepto | Archivo de implementación |
|---|---|---|
| Sección 3.2.3 | Database per Service | `database-init/01_create_databases.sql` + `02_create_users.sql` |
| Sección 11.0 | SAGA orquestada síncrona | `commerce-service/app/services/checkout_saga.py` |
| Sección 12.0 | Circuit Breaker + reintentos | `payment-service/app/core/circuit_breaker.py` + `gateway_client.py` |
| Sección 13.1 | Cache-Aside Redis | `catalog-service/app/core/cache.py` |
| Sección 13.5 | Lock distribuido Redis | `inventory-service/app/core/redis_lock.py` |
| Sección 18.5 | Latency Monkey (CB) | `scripts/chaos/latency_monkey_payment.sh` |
| Sección 18.8 | Conformity Monkey (DB aislamiento) | `scripts/chaos/conformity_monkey.sh` |
| Sección 18.9 | Security Monkey | `scripts/chaos/security_monkey.sh` |
| Sección 19.0 | Niveles de alcance | Nivel 1 + Nivel 2 implementados; Nivel 3 (RabbitMQ) fuera de scope |

---

## 7. Test del Mono — Chaos Engineering

El Simian Army implementado comprende 5 experimentos ejecutables como scripts bash. Los 4 de chaos están en `scripts/chaos/`. Total: **133 verificaciones / 133 PASS**.

### 7.1 Suite E2E — Flujo Completo

**Script:** `scripts/e2e/flujo_completo.sh`
**Propósito:** Valida el flujo de compra completo recorriendo los 5 microservicios en secuencia.
**Resultado esperado:** 34 PASS / 0 FAIL

| # | Hipótesis | Comando/Acción | Resultado Esperado | Resultado Real |
|---|---|---|---|---|
| H1 | Los 6 healthchecks responden 200 | `curl http://localhost/health/<svc>` × 6 | HTTP 200 en gateway, auth, catalog, inventory, commerce, payment | ✅ 6/6 PASS |
| H2 | Registro de cliente nuevo emite tokens y correo de bienvenida | `POST /api/auth/register` | 201 + access_token + refresh_token; email en Mailhog | ✅ PASS |
| H3 | Login con las credenciales recién creadas devuelve tokens | `POST /api/auth/login` | 200 + nuevo access_token | ✅ PASS |
| H4 | Login admin con credencial seed funciona | `POST /api/auth/login` admin@tienda.com | 200 + admin token | ✅ PASS |
| H5 | `GET /auth/me` retorna el perfil y role correcto | `GET /api/auth/me` + Bearer | 200 + email del cliente + role="customer" | ✅ PASS |
| H6 | Catálogo público retorna datos del seed | `GET /api/catalog` + `GET /api/products` | 200 + "Camiseta básica negra" en productos | ✅ PASS |
| H7 | Detalle de producto incluye variantes de Inventory (servicio distinto) | `GET /api/products/1` | inventory_available:true + sku:"CAM-NEG-S" | ✅ PASS |
| H8 | Carrito nuevo tiene 0 items | `GET /api/cart` + Bearer | item_count=0 | ✅ PASS |
| H9 | Agregar 2 productos + subtotal correcto | `POST /api/cart/items` × 2 | item_count=3, subtotal=133000.0 | ✅ PASS |
| H10 | Checkout con monto APPROVED (.00) crea Order PAID | `POST /api/checkout` Idempotency-Key | status="PAID", payment_status="APPROVED" | ✅ PASS |
| H11 | Stock real bajó en Inventory después del checkout | `GET /api/inventory/variants/1` | available < pre-checkout en ≥2 unidades | ✅ PASS |
| H12 | `/orders/mine` muestra el pedido recién creado | `GET /api/orders/mine` | order_code del checkout en la lista | ✅ PASS |
| H13 | History del pedido incluye transición a PAID | `GET /api/orders/{id}` | to_status="PAID" en history | ✅ PASS |
| H14 | Cliente tiene notificaciones in-app | `GET /api/notifications` | count ≥ 1 | ✅ PASS |
| H15 | Admin transiciona pedido: PAID→EN_PREPARACION→ENVIADO→ENTREGADO | `PATCH /api/admin/orders/{id}/status` × 3 | Cada transición devuelve el nuevo status | ✅ 3/3 PASS |
| H16 | Cliente puede crear reseña del producto entregado | `POST /api/reviews` rating=5 | 201 + review_id (pendiente de aprobación) | ✅ PASS |
| H17 | Admin aprueba reseña → Catalog actualiza rating | `PATCH /api/admin/reviews/{id}/approve` | products/1.average_rating ≥ 1.0 (Cache-Aside invalidado) | ✅ PASS |
| H18 | Sin token → 401; token customer en /admin → 403; clave mala → 401 | 3 requests negativos | 401, 403, 401 respectivamente | ✅ 3/3 PASS |
| H19 | Finance summary admin refleja la venta | `GET /api/admin/finance/summary` | gross_sales ≥ 133000 | ✅ PASS |

---

### 7.2 Chaos Monkey — Inventory

**Script:** `scripts/chaos/chaos_monkey_inventory.sh`
**Experimento:** Detiene el contenedor de Inventory y verifica que el sistema degrada gracefully sin crear Orders falsas.
**Resultado esperado:** 12 PASS / 0 FAIL

| # | Hipótesis | Comando | Resultado Esperado | Resultado Real |
|---|---|---|---|---|
| H1 | Sistema en estado normal inicial | Healthcheck × 6 | Todos 200 | ✅ PASS |
| H2 | Detener Inventory no afecta login | `docker compose stop inventory-service` → `POST /api/auth/login` | 200 (servicios no acoplados) | ✅ PASS |
| H3 | Catálogo sigue respondiendo con Inventory caído | `GET /api/products` | 200 (sin variantes de inventario; degradación graceful) | ✅ PASS |
| H4 | Checkout falla con 503 (inventory_unavailable) cuando Inventory está caído | `POST /api/checkout` | 503 code="inventory_unavailable" | ✅ PASS |
| H5 | NO se crea ninguna Order cuando Inventory está caído | `GET /api/orders/mine` | No hay nueva Order en PAID | ✅ PASS |
| H6 | `/health/inventory` devuelve 503 mientras Inventory está caído | `curl /health/inventory` | 503 o timeout | ✅ PASS |
| H7 | Reiniciar Inventory restaura el sistema | `docker compose start inventory-service` + esperar healthy | Healthcheck vuelve 200 | ✅ PASS |
| H8 | Checkout funciona normalmente después de restaurar | `POST /api/checkout` | Order PAID | ✅ PASS |

---

### 7.3 Latency Monkey — Circuit Breaker

**Script:** `scripts/chaos/latency_monkey_payment.sh`
**Experimento:** Fuerza 5 fallos consecutivos en la pasarela de pago (monto `.88` → mock 500) y verifica que el Circuit Breaker abre y protege el sistema.
**Resultado esperado:** 9 PASS / 0 FAIL

| # | Hipótesis | Comando | Resultado Esperado | Resultado Real |
|---|---|---|---|---|
| H1 | CB inicial en CLOSED | `GET /api/payments/circuit/state` | state="CLOSED" | ✅ PASS |
| H2 | 5 charges con monto .88 abren el CB | `POST /api/payments` × 5 con amount=50000.88 | Mock responde 500 × 5 veces | ✅ PASS |
| H3 | Tras 5 fallos, CB pasa a OPEN | `GET /api/payments/circuit/state` | state="OPEN", failures≥5 | ✅ PASS |
| H4 | Nuevo charge con CB OPEN rechazado en <500ms sin tocar la pasarela | `POST /api/payments` amount=50000.00 | 503 en <500ms (el mock no fue contactado) | ✅ PASS |
| H5 | Checkout con CB abierto devuelve 503 sin crear Order falsa | `POST /api/checkout` | 503 code="payment_unavailable" | ✅ PASS |
| H6 | Reserva de stock fue liberada (compensación SAGA) | `GET /api/inventory/variants/11` | available igual al pre-checkout | ✅ PASS |
| H7 | Reset admin del CB | `POST /api/payments/circuit/reset` | state="CLOSED" | ✅ PASS |
| H8 | Charge con monto .00 tras reset | `POST /api/payments` amount=50000.00 | status="APPROVED" | ✅ PASS |
| H9 | Checkout completo funciona después del reset | `POST /api/checkout` | Order PAID | ✅ PASS |

---

### 7.4 Conformity Monkey — Database per Service

**Script:** `scripts/chaos/conformity_monkey.sh`
**Experimento:** Verifica que cada microservicio cumple los estándares de la arquitectura (estructura de archivos, Dockerfile seguro, DB aislada, gateway routing).
**Resultado esperado:** 51 PASS / 0 FAIL

| Categoría | Hipótesis | Resultado Real |
|---|---|---|
| Estructura de archivos (5 servicios × 4 archivos) | Dockerfile, requirements.txt, .env.example, app/main.py existen en cada servicio | ✅ 20/20 PASS |
| Dockerfile no-root (5 servicios) | Cada Dockerfile declara `USER` no-root por seguridad | ✅ 5/5 PASS |
| Healthchecks directos (5 puertos) | Cada servicio responde en su puerto propio con service name correcto | ✅ 5/5 PASS |
| Gateway routing (5 servicios) | Gateway enruta correctamente `/api/<svc>` a cada upstream | ✅ 5/5 PASS |
| Database per Service — aislamiento real | `auth_user` no puede acceder a `catalog_db`; `catalog_user` no puede acceder a `auth_db`; etc. | ✅ ≥16 PASS |

---

### 7.5 Security Monkey

**Script:** `scripts/chaos/security_monkey.sh`
**Experimento:** Audita defensas de seguridad (autenticación, autorización, IDOR, headers, rate limit).
**Resultado esperado:** 27 PASS / 0 FAIL

| Categoría | Hipótesis | Resultado Real |
|---|---|---|
| Security headers (3) | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` presentes | ✅ 3/3 PASS |
| Sin token → 401 (7 rutas) | `/auth/me`, `/cart`, `/orders/mine`, `/notifications`, `/admin/*` sin token → 401 | ✅ 7/7 PASS |
| JWT corrupto → 401 (2 casos) | `Bearer not.a.jwt` y JWT con firma inválida → 401 | ✅ 2/2 PASS |
| Rol insuficiente → 403 (6 rutas) | Token customer en `/admin/*` → 403 | ✅ 6/6 PASS |
| IDOR — pedidos ajenos → 404 (2) | Cliente A no puede ver pedidos de Cliente B | ✅ 2/2 PASS |
| Rate limit login (2) | 6 logins rápidos → el 6to recibe 429 | ✅ 2/2 PASS |
| No leak de tokens en logs (1) | `docker compose logs` no contiene strings de JWT | ✅ 1/1 PASS |
| **Total** | | **✅ 27/27 PASS** |

---

### 7.6 Resumen Total

| Script | Verificaciones | Resultado |
|---|---|---|
| `scripts/e2e/flujo_completo.sh` | 34 | ✅ 34/34 PASS |
| `scripts/chaos/conformity_monkey.sh` | 51 | ✅ 51/51 PASS |
| `scripts/chaos/security_monkey.sh` | 27 | ✅ 27/27 PASS |
| `scripts/chaos/chaos_monkey_inventory.sh` | 12 | ✅ 12/12 PASS |
| `scripts/chaos/latency_monkey_payment.sh` | 9 | ✅ 9/9 PASS |
| **TOTAL** | **133** | **✅ 133/133 PASS** |

---

## 8. Decisiones Técnicas y Justificaciones

### 8.1 Database per Service en variante lógica (no física)

**Decisión:** Una sola instancia MySQL con 5 schemas separados y un usuario por servicio con `GRANT` exclusivo.

**Justificación:** Proporciona el aislamiento real de datos (ningún usuario puede acceder al schema de otro servicio — verificado por Conformity Monkey) sin el costo operativo de 5 instancias MySQL separadas, lo cual sería inmanejable en un entorno académico. En producción real, cada schema podría migrarse a su propia instancia o RDS sin cambiar el código de la aplicación (solo la `DATABASE_URL` en `.env`).

### 8.2 SAGA Orquestada Síncrona (Nivel 1 de alcance)

**Decisión:** Commerce coordina directamente las llamadas REST a Inventory y Payment, esperando cada respuesta antes del siguiente paso.

**Justificación:** La SAGA asíncrona con AMQP (Nivel 3) requiere RabbitMQ, Outbox Pattern y DLQ, triplicando la complejidad de infraestructura. La variante síncrona es funcionalmente correcta para el volumen académico, implementa compensaciones reales y es completamente demostrable. La coreografía AMQP queda documentada como evolución futura.

### 8.3 Outbox Pattern simplificado

**Decisión:** El commit final de la SAGA persiste la Order y los ítems en una transacción MySQL, pero la confirmación a Inventory es un paso HTTP previo (fuera de la transacción). Si el commit final falla, el stock puede quedar inconsistente.

**Justificación:** El Outbox Pattern completo requeriría una tabla de outbox, un worker de mensajería y RabbitMQ. Para el MVP académico, la probabilidad de fallo entre la llamada HTTP a Inventory y el commit de la Order es extremadamente baja. El caso de inconsistencia está documentado en el código y el scheduler de Inventory libera la reserva vencida como medida de reconciliación.

### 8.4 Payment Mock con respuestas deterministas

**Decisión:** La pasarela de pago es un FastAPI local que responde según los centavos del monto enviado.

**Justificación:** Permite demostrar los 4 escenarios críticos (APPROVED, REJECTED, PENDING, FAILED) de forma reproducible y sin dependencias externas, facilitando las pruebas automatizadas del Circuit Breaker y la SAGA.

---

## 9. Estructura del Repositorio

```
tienda-digital-master/
├── api-gateway/
│   ├── Dockerfile                    # nginx:1.27-alpine
│   ├── nginx.conf                    # configuración base + logging
│   └── conf.d/
│       └── gateway.conf              # upstreams, routing, CORS, seguridad
├── services/
│   ├── auth-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── .env.example
│   │   └── app/
│   │       ├── main.py               # lifespan: crea tablas + seed admin
│   │       ├── api/auth.py           # register, login, refresh, logout, me
│   │       ├── api/users.py          # perfil usuario
│   │       ├── api/admin.py          # customers, access-logs
│   │       ├── core/security.py      # JWT HS256, bcrypt, validación
│   │       ├── core/database.py      # SQLAlchemy engine
│   │       ├── models/entities.py    # User, RefreshToken, AccessLog
│   │       └── services/mailer.py    # SMTP bienvenida
│   ├── catalog-service/
│   │   └── app/
│   │       ├── core/cache.py         # Cache-Aside Redis
│   │       ├── api/public.py         # GET products, categories
│   │       └── services/inventory_client.py  # REST call a Inventory
│   ├── inventory-service/
│   │   └── app/
│   │       ├── core/redis_lock.py    # Distributed Lock
│   │       ├── api/internal.py       # reserve, confirm, release
│   │       └── services/scheduler.py # expiración de reservas
│   ├── commerce-service/
│   │   └── app/
│   │       ├── services/checkout_saga.py  # Orquestador SAGA
│   │       ├── api/cart.py
│   │       ├── api/checkout.py
│   │       └── api/orders.py
│   └── payment-service/
│       └── app/
│           ├── core/circuit_breaker.py    # Circuit Breaker Redis
│           ├── api/payments.py
│           └── services/gateway_client.py # reintentos backoff
├── payment-mock/
│   └── app/main.py                   # FastAPI simulador 4 escenarios
├── database-init/
│   ├── 01_create_databases.sql       # 5 schemas
│   └── 02_create_users.sql           # 5 usuarios GRANT exclusivo
├── database/
│   ├── schema.sql                    # schema legado monolito (referencia)
│   └── seed.sql                      # seed legado monolito
├── scripts/
│   ├── _helpers.sh                   # funciones compartidas (assert, ok, fail)
│   ├── e2e/flujo_completo.sh         # 34 verificaciones E2E
│   └── chaos/
│       ├── conformity_monkey.sh      # 51 verificaciones conformidad
│       ├── security_monkey.sh        # 27 verificaciones seguridad
│       ├── chaos_monkey_inventory.sh # 12 verificaciones degradación
│       └── latency_monkey_payment.sh # 9 verificaciones Circuit Breaker
├── frontend/                         # React + Vite → http://localhost/api
├── backend_legacy_monolito/          # Monolito Fase 1 (referencia histórica)
├── docs/
│   ├── arquitectura.md
│   ├── endpoints.md
│   ├── fase2.md
│   ├── chaos.md
│   ├── instalacion.md
│   └── pruebas.md
├── docker-compose.yml                # 11 contenedores, red tienda_net
└── README.md
```

---

## 10. Requisitos Funcionales y No Funcionales Cubiertos

| Req. | Descripción | Implementado en |
|---|---|---|
| RF-01 | Registro y autenticación de usuarios | Auth Service — `/api/auth/register`, `/api/auth/login` |
| RF-02 | Gestión de catálogo de productos | Catalog Service — `/api/products`, Cache-Aside |
| RF-03 | Gestión de inventario y variantes | Inventory Service — variantes, stock, movimientos |
| RF-04 | Carrito de compras | Commerce Service — `/api/cart` |
| RF-05 | Proceso de checkout con pago | Commerce Service — `/api/checkout` + SAGA |
| RF-06 | Historial de pedidos | Commerce Service — `/api/orders/mine`, `/api/orders/{id}` |
| RF-07 | Reseñas de productos | Commerce Service — `/api/reviews` → Catalog rating |
| RF-08 | Notificaciones al usuario | Commerce Service — `/api/notifications` + correo Mailhog |
| RF-09 | Panel de administración | Admin endpoints en todos los servicios |
| RNF-01 | Rendimiento (Cache-Aside) | Catalog Service — Redis TTL 60-300s |
| RNF-02 | Resiliencia y tolerancia a fallos | Circuit Breaker + SAGA compensaciones + degradación graceful |
| RNF-03 | Trazabilidad | Correlation ID en todos los servicios + AccessLog + OrderAuditLog |

---

## 11. Conclusiones

La implementación de la Fase 2 materializa de forma ejecutable y verificable los patrones de arquitectura de microservicios estudiados en el curso.

**Logros principales:**
1. **Migración completa y funcional** del monolito FastAPI a 5 microservicios independientes, desplegables con un solo comando Docker Compose.
2. **Patrones reales, no simulados:** SAGA, Circuit Breaker, Cache-Aside, Distributed Lock y Database per Service están implementados en código, no solo documentados.
3. **Chaos Engineering real:** 133 verificaciones automatizadas demuestran comportamiento correcto tanto en happy path como en escenarios de fallo.
4. **Separación de responsabilidades:** cada servicio tiene su propio schema, código, Dockerfile y conjunto de endpoints sin compartir código con los demás.
5. **Monolito preservado:** `backend_legacy_monolito/` conserva la evidencia del punto de partida de la migración.

**Limitaciones aceptadas para el MVP académico:**
- Outbox Pattern simplificado (riesgo de inconsistencia en caso de fallo del commit final documentado en el código).
- SAGA síncrona REST en lugar de coreografía AMQP (Nivel 3).
- RabbitMQ / DLQ fuera de scope (Nivel 3).

Estas limitaciones son coherentes con los niveles de alcance definidos en el informe de Fase 1 (sección 19.0) y con el tiempo disponible en el curso.
