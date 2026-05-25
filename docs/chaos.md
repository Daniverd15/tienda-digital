# Chaos Engineering - Tienda Digital

Runbook y resultados de los experimentos de Chaos Engineering aplicados a la
arquitectura de microservicios. Implementa lo planteado en el Informe Fase 1
seccion 18 (Prueba del Mono).

## Scripts ejecutables

| Script | Categoria del Simian Army | Hipotesis que valida |
|---|---|---|
| `scripts/e2e/flujo_completo.sh` | Smoke E2E completo | El flujo de compra cruza los 5 microservicios |
| `scripts/chaos/chaos_monkey_inventory.sh` | Chaos Monkey | Detener Inventory durante un checkout NO crea pedidos PAID falsos |
| `scripts/chaos/latency_monkey_payment.sh` | Latency Monkey + Circuit Breaker | Fallas repetidas de la pasarela abren el CB; el checkout degrada graceful |
| `scripts/chaos/conformity_monkey.sh` | Conformity Monkey | Cada microservicio cumple los estandares (health, USER no-root, DB aislada) |
| `scripts/chaos/security_monkey.sh` | Security Monkey | Authz/Authn estricta + headers + no leaks de pedidos ajenos |

## Como ejecutar todos los experimentos

```bash
# Precondiciones
docker compose up --build -d
# Esperar a que todos los servicios queden healthy
docker compose ps

# Suite completa (orden recomendado)
bash scripts/e2e/flujo_completo.sh             # 34 PASS
bash scripts/chaos/conformity_monkey.sh        # 51 PASS
bash scripts/chaos/security_monkey.sh          # 27 PASS
bash scripts/chaos/chaos_monkey_inventory.sh   # 12 PASS  (DETIENE inventory; tras correr recupera)
bash scripts/chaos/latency_monkey_payment.sh   #  9 PASS  (abre CB y lo resetea)
```

Total: **133 verificaciones ejecutables** que validan el comportamiento del
sistema frente a las cinco categorias canonicas del Simian Army.

## Resultado consolidado (ultima corrida)

| Suite | PASS / TOTAL | Observaciones |
|---|---|---|
| flujo_completo.sh | 34 / 34 | Registra cliente, compra completa, admin transiciona, review, finance |
| chaos_monkey_inventory.sh | 12 / 12 | Catalog sigue; checkout degrada a SIN_STOCK; recuperacion automatica |
| latency_monkey_payment.sh | 9 / 9 | CB abre en 5 fallos; rechazo en 79ms; checkout PAGO_PENDIENTE; reset OK |
| conformity_monkey.sh | 51 / 51 | DB per Service aislada con GRANT; estandares por servicio |
| security_monkey.sh | 27 / 27 | 401/403 estrictos; rate limit; no leak pedidos ajenos; headers OK |
| **TOTAL** | **133 / 133** | |

## Detalle de cada experimento

### 1. Chaos Monkey - Inventory caido durante checkout

**Hipotesis** (informe Fase 1, diagrama 18.4):
1. El catalogo sigue respondiendo (modo degradado con `inventory_available=false`)
2. El detalle de producto marca `inventory_available: false` cuando Inventory esta caido
3. El gateway devuelve 5xx para `/api/inventory/*`
4. El checkout responde con estado controlado (`SIN_STOCK`/`PAGO_PENDIENTE`), NUNCA `PAID` falso
5. Al restaurar Inventory, el sistema vuelve a operar normal
6. Nuevo checkout funciona normal tras la recuperacion

**Comando:** `docker compose stop inventory-service` y curl al flujo.
**Recuperacion:** `docker compose start inventory-service` (automatico en el script).

### 2. Latency Monkey + Circuit Breaker

**Hipotesis** (informe Fase 1, diagrama 18.5):
1. Tras 5 fallos consecutivos (monto .88 = mock devuelve 500), CB pasa a `OPEN`
2. Nuevas llamadas con CB abierto responden 503 en < 100ms sin tocar la pasarela
3. El checkout completo con CB abierto degrada a `Order(PAGO_PENDIENTE)`
4. `POST /payments/circuit/reset` (admin) restaura `CLOSED`
5. Charges nuevos tras reset funcionan normal

**Comando:** 5 POST /api/payments con `amount=50000.88`.
**Inspeccion:** `GET /api/payments/circuit/state` (admin).
**Reset:** `POST /api/payments/circuit/reset` (admin).

### 3. Conformity Monkey

**Estandares verificados por cada microservicio:**
- Presencia de `Dockerfile`, `requirements.txt`, `.env.example`, `app/main.py`
- Dockerfile declara `USER appuser` (no root)
- Endpoint `/health` responde 200 con `service: <nombre>-service`
- Endpoint `/` reporta `version`
- Healthchecks de Docker Compose marcan `(healthy)`
- Gateway enruta correctamente los 5 servicios
- **Database per Service real**: cada `<svc>_user` puede leer su `<svc>_db`
  pero NO puede leer otra base (aislamiento por GRANT validado)

### 4. Security Monkey

**Validaciones de seguridad:**
- Headers `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` en gateway
- `/auth/me`, `/cart`, `/orders/mine`, `/notifications`, `/admin/*` sin JWT -> 401
- JWT corrupto / firma invalida -> 401
- Token de customer pidiendo `/admin/*` -> 403 (6 endpoints validados)
- Token de admin accede a todo el panel admin
- **Aislamiento por usuario**: customer NO ve pedidos de otro user_id (404)
- Rate limit en `/auth/login` (al menos 1 bloqueo de 15 intentos)
- Logs del gateway no contienen JWTs
- Redis no responde a HTTP (correcto, protocolo TCP)

### 5. Doctor Monkey y Janitor Monkey

**Doctor Monkey** se materializa con los healthchecks profundos de cada
servicio (`/health` valida MySQL y Redis cuando aplica) y el endpoint
`GET /api/payments/circuit/state` (admin) para inspeccion del CB.

**Janitor Monkey** se materializa con:
- Scheduler asyncio en Inventory: libera reservas vencidas cada 60s
- Worker async en Payment: reconcilia pagos PENDING/FAILED cada 5min
- `POST /api/admin/inventory/expire-pending` para forzar el scheduler

## Que pasa si un experimento falla

Cada script imprime `FAIL` con el contexto (esperado vs actual). El criterio
de exito es `0 FAIL`. Si un experimento deja el sistema en estado degradado:

```bash
# Restaurar todo
docker compose down && docker compose up -d

# Si quedo el CB abierto
ADMIN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tienda.com","password":"Admin1234*"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -X POST http://localhost/api/payments/circuit/reset -H "Authorization: Bearer $ADMIN"
```

## Trazabilidad con el informe Fase 1

| Seccion del informe | Implementacion ejecutable |
|---|---|
| 18.1 Mapa del Mono sobre la arquitectura | Conformity + Security cubren los componentes |
| 18.3 Ciclo de vida de un experimento | Cada script sigue: precondicion -> hipotesis -> ejecucion -> observacion -> restauracion |
| 18.4 Chaos Monkey sobre Inventory | `scripts/chaos/chaos_monkey_inventory.sh` |
| 18.5 Latency Monkey + Circuit Breaker | `scripts/chaos/latency_monkey_payment.sh` |
| 18.6 Doctor Monkey | `/health` profundos + `/circuit/state` |
| 18.7 Janitor Monkey | Schedulers + reconciler asyncio |
| 18.8 Conformity Monkey | `scripts/chaos/conformity_monkey.sh` |
| 18.9 Security Monkey | `scripts/chaos/security_monkey.sh` |
| 18.10 Casos de fallo por componente | Cubierto en los 4 scripts de chaos |
| 18.12 Protocolo paso a paso | Codificado en cada script (precondicion + hipotesis + verificacion) |
