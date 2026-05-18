# Fase 2 - Migracion a arquitectura de microservicios

Bitacora del proceso de transformacion del monolito FastAPI a la arquitectura
de microservicios planteada en el informe de Fase 1 (MVP de 5 servicios).

## Bloques de trabajo

| # | Bloque | Estado | Autor | Resultado validado |
|---|---|---|---|---|
| 1 | Scaffolding + infra (gateway, MySQL multi-schema, Redis, Mailhog, payment-mock) | DONE | Tomas | `docker compose up` levanta todo; los 6 `/health/<svc>` responden 200 a traves del gateway |
| 2 | Auth & Users Service completo + gateway con rewrites uniformes | DONE | Santiago / Tomas | Registro, login, refresh, logout, me, /users/me, /admin/me, /admin/customers, /admin/access-logs. Correo de bienvenida llega a Mailhog. Bitacora con correlation_id. |
| 3 | Catalog Service completo + Cache-Aside Redis | DONE | Santiago | Endpoints publicos: /catalog (overview), /categories, /products, /products/{id}, /store/settings, /store/messages. Endpoints admin CRUD para categorias, productos, store, mensajes, rating. Cache TTL 60-300s con invalidacion al editar. Llamada REST a Inventory para enriquecer detalle. Seed: 3 categorias, 5 productos. Gateway con healthcheck via curl. |
| 4 | Inventory Service completo (locks distribuidos + scheduler) | DONE | Santiago | 11 variantes sembradas. Reserve/Confirm/Release con lock distribuido Redis y SELECT FOR UPDATE. Concurrencia validada: 2 reservas simultaneas de 3u sobre stock=4 -> una pasa, otra 409. Scheduler libera reservas vencidas cada 60s. CRUD admin de variantes + movimientos manuales + alertas de stock minimo. Catalog ya enriquece detalle de producto con variantes reales. |
| 5 | Payment basico + Commerce completo + SAGA orquestada sincrona | DONE | Santiago | Payment Service basico (POST /payments contra mock; 4 escenarios APPROVED/REJECTED/PENDING/FAILED). Commerce Service completo: carrito, checkout con SAGA orquestada sincrona REST (reserve->charge->confirm/release), pedidos con historia, reviews con validacion de pedido entregado, notificaciones in-app + correos SMTP, admin para pedidos/empleados/gastos/finanzas/reviews/audit. Validacion E2E: registro + carrito (2 productos) + checkout APPROVED -> orden PAID, stock baja en Inventory, 4 notificaciones + 5 correos Mailhog; admin transiciona PAID -> EN_PREPARACION -> ENVIADO -> ENTREGADO; cliente crea review -> Catalog rating se actualiza a 5.0. Pago REJECTED -> compensacion automatica: stock vuelve, orden PAGO_RECHAZADO. Transiciones invalidas rechazadas con 409. |
| 6 | Endurecer Payment con Circuit Breaker + reconciler | DONE | Santiago | CB Redis (threshold=5, open_ttl=60s, estados CLOSED/OPEN/HALF_OPEN); reintentos con backoff exponencial (250ms, 500ms, 1s) en errores transitorios; endpoints admin GET /api/payments/circuit/state, POST /api/payments/circuit/reset, POST /api/payments/{id}/reconcile; worker async cada 5 min reintenta PENDING/FAILED automaticamente. Chaos validado: 5 charges con monto .88 abren el CB; siguientes charges rechazados con 503 sin tocar pasarela; checkout completo con CB abierto degrada graceful a Order(PAGO_PENDIENTE) con stock reservado; reset admin restaura CLOSED. Tests CB: 4 PASS. |
| 7 | Frontend apuntando al gateway | DONE | Daniel | VITE_API_URL -> http://localhost/api. Migracion de rutas: /orders/my -> /orders/mine; /products/search -> /products; /payments/simulate + /orders -> /checkout (SAGA en un solo paso); /admin/dashboard -> /admin/finance/summary (con adaptador inline); /admin/settings -> /admin/store/settings; /admin/customers/{id}/orders -> /admin/orders?user_id=; /admin/products/{id}/variants -> /admin/inventory/variants?product_id=; /admin/categories/{id}/archive -> DELETE /admin/categories/{id}; PUT /admin/orders/{id}/status -> PATCH con body {new_status}; PUT /notifications/{id}/read -> PATCH; /admin/reviews/{id}?approved -> PATCH approve / DELETE; /products/{id}/reviews -> /reviews/product/{id}. Badge.jsx soporta ambos vocabularios (microservicios MAYUSCULAS + monolito minusculas). PaymentResult.jsx ejecuta SAGA completa con offset de centavos para simular APPROVED/REJECTED/PENDING. Endpoints no migrados (/admin/upload-image, /admin/customers/{id}/status) degradan con stub. Reportes CSV/PDF generados en cliente desde finance/summary. Vite corre en :5173, CORS verificado, login y catalog responden 200. |
| 8 | Pruebas E2E + experimento de Chaos | pendiente | Tomas | Evidencia funcional |
| 9 | Documentacion final | pendiente | Tomas | README + endpoints + chaos.md |

## Decisiones de migracion

- **Coexistencia con el monolito legacy**: el directorio `backend/` se conserva mientras
  los microservicios maduran. Sigue ejecutandose con `uvicorn backend.main:app --port 8000`
  apuntando al esquema `tienda_digital` de la misma instancia MySQL. Se retirara al
  finalizar el Bloque 8.
- **Database per Service en variante logica**: una sola instancia MySQL con cinco
  esquemas separados (`auth_db`, `catalog_db`, `inventory_db`, `commerce_db`,
  `payments_db`) y un usuario por servicio con GRANT exclusivo sobre su esquema.
  Justificacion en informe Fase 1, seccion 3.2.3.
- **SAGA orquestada sincrona como punto de partida** (Nivel 1 de alcance del informe).
  Commerce coordina las llamadas REST a Inventory y Payment con compensaciones HTTP.
  La migracion a coreografia AMQP queda como Nivel 3.
- **Frontend sin cambios estructurales**: la React SPA se conservara identica; solo se
  ajustara `frontend/src/api/client.js` en el Bloque 7 para apuntar al API Gateway
  (`http://localhost/api` en vez de `http://localhost:8000`).

## Bloque 1 - Resultado validado

```
$ docker compose ps
NAME                    STATUS         PORTS
tienda_auth             Up (healthy)   0.0.0.0:8001->8001/tcp
tienda_catalog          Up (healthy)   0.0.0.0:8002->8002/tcp
tienda_commerce         Up (healthy)   0.0.0.0:8004->8004/tcp
tienda_digital_mysql    Up (healthy)   0.0.0.0:3306->3306/tcp
tienda_gateway          Up             0.0.0.0:80->80/tcp
tienda_inventory        Up (healthy)   0.0.0.0:8003->8003/tcp
tienda_mailhog          Up             0.0.0.0:1025->1025/tcp, 0.0.0.0:8025->8025/tcp
tienda_payment          Up (healthy)   0.0.0.0:8005->8005/tcp
tienda_payment_mock     Up (healthy)   0.0.0.0:9000->9000/tcp
tienda_phpmyadmin       Up             0.0.0.0:8080->80/tcp
tienda_redis            Up (healthy)   0.0.0.0:6379->6379/tcp

$ for s in gateway auth catalog inventory commerce payment; do
    curl -s http://localhost/health/$s; echo
  done
{"status":"ok","service":"api-gateway"}
{"status":"ok","service":"auth-service"}
{"status":"ok","service":"catalog-service"}
{"status":"ok","service":"inventory-service"}
{"status":"ok","service":"commerce-service"}
{"status":"ok","service":"payment-service"}

$ docker compose exec -T mysql mysql -uroot -proot_password -e "SHOW DATABASES;"
auth_db
catalog_db
commerce_db
inventory_db
payments_db
tienda_digital   <- monolito legacy preservado
```

## Como levantar el entorno (Bloque 1)

```bash
# Construir e iniciar todos los contenedores
docker compose up --build -d

# Verificar estado
docker compose ps

# Validar healthchecks
curl http://localhost/health/gateway
curl http://localhost/health/auth
curl http://localhost/health/catalog
curl http://localhost/health/inventory
curl http://localhost/health/commerce
curl http://localhost/health/payment

# Probar la pasarela mock directamente
curl -X POST http://localhost:9000/charge \
  -H "Content-Type: application/json" \
  -d '{"order_code":"DEMO","amount":50000.00}'

# Detener
docker compose down
```

## Bloque 2 - Auth Service: validacion E2E

```bash
# Login admin (seed)
curl -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tienda.com","password":"Admin1234*"}'
# -> {access_token, refresh_token, user{role: admin}}

# Registro cliente
curl -X POST http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Cliente Demo","email":"demo@cliente.com","phone":"3001112233","password":"Cliente1234*"}'
# -> 201 + tokens + correo de bienvenida en Mailhog (http://localhost:8025)

# Detalle de usuario actual
curl http://localhost/api/auth/me -H "Authorization: Bearer <access_token>"

# Refresh (rota el refresh; el viejo queda revocado)
curl -X POST http://localhost/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh>"}'

# Listar clientes (solo admin)
curl http://localhost/api/admin/customers -H "Authorization: Bearer <admin_access_token>"

# Bitacora de accesos (login, register, refresh, login_failed)
curl http://localhost/api/admin/access-logs -H "Authorization: Bearer <admin_access_token>"
```

Casos de error validados:
- 401 sin token
- 401 con credenciales invalidas
- 403 con token de customer pidiendo recurso admin
- 422 con contrasena debil

Credenciales seed por defecto:
- admin@tienda.com / Admin1234*

## Puertos asignados

| Servicio | Puerto host | URL |
|---|---|---|
| API Gateway (Nginx) | 80 | http://localhost |
| Auth Service | 8001 | http://localhost:8001 |
| Catalog Service | 8002 | http://localhost:8002 |
| Inventory Service | 8003 | http://localhost:8003 |
| Commerce Service | 8004 | http://localhost:8004 |
| Payment Service | 8005 | http://localhost:8005 |
| Payment mock | 9000 | http://localhost:9000 |
| MySQL | 3306 | mysql://localhost:3306 |
| phpMyAdmin | 8080 | http://localhost:8080 |
| Redis | 6379 | redis://localhost:6379 |
| Mailhog SMTP | 1025 | smtp://localhost:1025 |
| Mailhog UI | 8025 | http://localhost:8025 |
