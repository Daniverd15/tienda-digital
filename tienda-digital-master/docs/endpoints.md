# Endpoints - Arquitectura de microservicios

Todos los endpoints publicos pasan por el API Gateway en `http://localhost/api/...`.
Los healthchecks de cada servicio se exponen en `http://localhost/health/<svc>`.

- **Autenticacion:** JWT HS256 con un `JWT_SECRET` compartido. Cada servicio valida
  el token localmente; no se realizan llamadas de vuelta al Auth Service.
- **Rol:** se infiere del claim `role` del JWT (`customer` o `admin`).
- **Cuerpos:** JSON salvo cuando se indique. `Content-Type: application/json`.
- **Correlation ID:** el gateway inyecta `X-Correlation-Id` y se propaga a logs.
- **Convenciones:** sin slash al final. El gateway reescribe el prefijo
  `/api/<svc>` al path interno del servicio.

## 1. Auth Service - puerto 8001

Prefijo gateway: `/api/auth`, `/api/users`, `/api/admin/me`, `/api/admin/customers`, `/api/admin/access-logs`.

| Metodo | Endpoint | Descripcion | Rol |
|---|---|---|---|
| POST | `/api/auth/register` | Registro de cliente. Envia correo de bienvenida via Mailhog. | Publico |
| POST | `/api/auth/login` | Inicio de sesion. Devuelve `access_token` + `refresh_token`. Rate limit (5 req/min/IP). | Publico |
| POST | `/api/auth/refresh` | Rota el refresh token; el viejo queda revocado. | Cliente/Admin |
| POST | `/api/auth/logout` | Cierre de sesion (registra evento). | Cliente/Admin |
| GET | `/api/auth/me` | Usuario actual. | Cliente/Admin |
| GET | `/api/users/me` | Perfil del usuario actual. | Cliente/Admin |
| PUT | `/api/users/me` | Actualiza perfil del usuario actual. | Cliente/Admin |
| GET | `/api/admin/me` | Perfil del administrador autenticado. | Admin |
| PUT | `/api/admin/me` | Actualiza perfil de administrador. | Admin |
| GET | `/api/admin/customers` | Lista de clientes. | Admin |
| GET | `/api/admin/customers/{id}` | Detalle de cliente. | Admin |
| GET | `/api/admin/access-logs` | Bitacora de logins, registros y refresh. | Admin |
| GET | `/health/auth` | Salud del servicio (MySQL conectado). | Publico |

## 2. Catalog Service - puerto 8002

Prefijo gateway: `/api/catalog`, `/api/products`, `/api/categories`, `/api/store`, `/api/admin/catalog`, `/api/admin/products`, `/api/admin/categories`, `/api/admin/store`, `/api/admin/messages`.

Cache-Aside con Redis (TTL 60-300s, invalidacion al editar).

### Publico
| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET | `/api/catalog` | Overview general (productos destacados + categorias + tienda). |
| GET | `/api/store/settings` | Configuracion de la tienda visible al publico. |
| GET | `/api/store/messages` | Mensajes informativos activos. |
| GET | `/api/categories` | Categorias activas. |
| GET | `/api/products` | Productos activos. Soporta `?q=`, `?category_id=`. |
| GET | `/api/products/{id}` | Detalle de producto. Enriquece con variantes reales via call REST a Inventory. |

### Admin
| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET / POST | `/api/admin/categories` | Listar / crear categoria. |
| PUT / DELETE | `/api/admin/categories/{id}` | Editar / archivar categoria. |
| GET / POST | `/api/admin/products` | Listar / crear producto. |
| PUT / DELETE | `/api/admin/products/{id}` | Editar / archivar producto. |
| GET | `/api/admin/products/{id}/images` | Listar imagenes del producto. |
| POST | `/api/admin/products/{id}/images` | Agregar imagen (multipart/form-data). |
| DELETE | `/api/admin/products/{id}/images/{image_id}` | Eliminar imagen. |
| PUT | `/api/admin/products/{id}/rating` | Recalcular rating (lo llama Commerce al aprobar resena). |
| GET / PUT | `/api/admin/store/settings` | Ver / editar configuracion de la tienda. |
| GET / POST | `/api/admin/messages` | Listar / crear mensaje informativo. |
| PUT / DELETE | `/api/admin/messages/{id}` | Editar / archivar mensaje. |
| GET | `/health/catalog` | Salud del servicio. |

## 3. Inventory Service - puerto 8003

Prefijo gateway: `/api/inventory`, `/api/variants`, `/api/admin/inventory`, `/api/admin/variants`.

Lock distribuido Redis (`SET NX EX` + Lua release-by-token) + `SELECT FOR UPDATE`.
Scheduler interno expira reservas vencidas cada 60s.

### Publico / interno
| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET | `/api/inventory/products/{product_id}/variants` | Variantes activas (lo usa Catalog para enriquecer detalle). |
| GET | `/api/inventory/variants/{variant_id}` | Detalle de variante. |

### Interno (orquestado por Commerce SAGA)
| Metodo | Endpoint | Descripcion |
|---|---|---|
| POST | `/api/inventory/reserve` | Reserva atomica de items con lock distribuido + SELECT FOR UPDATE. |
| POST | `/api/inventory/confirm/{order_id}` | Confirma reserva (descuenta stock real). |
| POST | `/api/inventory/release` | Libera reserva (compensacion de la SAGA si Payment REJECTED). |

### Admin
| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET / POST | `/api/admin/variants` | Listar / crear variante (acepta `?product_id=`). |
| PUT / DELETE | `/api/admin/variants/{variant_id}` | Editar / desactivar variante. |
| GET / POST | `/api/admin/inventory/movements` | Listar / crear movimiento manual. |
| GET | `/api/admin/inventory/alerts` | Alertas de stock minimo. |
| POST | `/api/admin/inventory/alerts/scan` | Escaneo manual de stock minimo. |
| POST | `/api/admin/inventory/alerts/{id}/resolve` | Marcar alerta como resuelta. |
| POST | `/api/admin/inventory/expire-pending` | Forzar expiracion de reservas pendientes. |
| GET | `/health/inventory` | Salud del servicio. |

## 4. Commerce Service - puerto 8004

Prefijo gateway: `/api/cart`, `/api/checkout`, `/api/orders`, `/api/reviews`, `/api/notifications`, `/api/admin/orders`, `/api/admin/employees`, `/api/admin/expenses`, `/api/admin/finance`, `/api/admin/reviews`, `/api/admin/audit-logs`.

Orquestador de la SAGA orquestada sincrona REST:
`reserve -> charge -> confirm (APPROVED) | release (REJECTED)`.

### Carrito (cliente)
| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET | `/api/cart` | Carrito abierto del cliente. |
| POST | `/api/cart/items` | Agregar item. |
| PUT | `/api/cart/items/{id}` | Cambiar cantidad. |
| DELETE | `/api/cart/items/{id}` | Eliminar item. |
| DELETE | `/api/cart` | Vaciar carrito. |

### Checkout (cliente)
| Metodo | Endpoint | Descripcion |
|---|---|---|
| POST | `/api/checkout` | Ejecuta la SAGA completa. Header `Idempotency-Key` requerido. Devuelve `Order` con estado `PAID`, `PAGO_RECHAZADO` o `PAGO_PENDIENTE` (degradacion graceful si CB abierto). |

### Pedidos (cliente)
| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET | `/api/orders/mine` | Historial de pedidos del cliente. |
| GET | `/api/orders/{order_id}` | Detalle de pedido propio (404 si no es del usuario). |

### Resenas (cliente)
| Metodo | Endpoint | Descripcion |
|---|---|---|
| POST | `/api/reviews` | Crear resena (requiere orden ENTREGADO del cliente). Dispara `PUT` a Catalog para recalcular rating. |
| GET | `/api/reviews/mine` | Mis resenas. |
| GET | `/api/reviews/product/{product_id}` | Resenas aprobadas de un producto (publico). |

### Notificaciones (cliente)
| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET | `/api/notifications` | Notificaciones in-app. |
| PATCH | `/api/notifications/{id}/read` | Marcar como leida. |
| PATCH | `/api/notifications/read-all` | Marcar todas como leidas. |

### Admin
| Metodo | Endpoint | Descripcion |
|---|---|---|
| GET | `/api/admin/orders` | Pedidos (filtros `?status=`, `?user_id=`). |
| GET | `/api/admin/orders/{order_id}` | Detalle de pedido. |
| PATCH | `/api/admin/orders/{order_id}/status` | Transicion de estado (`{"new_status":"EN_PREPARACION"}`). |
| GET / POST | `/api/admin/employees` | Listar / crear empleado. |
| PUT / DELETE | `/api/admin/employees/{id}` | Editar / archivar empleado. |
| GET / POST | `/api/admin/expenses` | Listar / registrar gasto. |
| DELETE | `/api/admin/expenses/{id}` | Eliminar gasto. |
| GET | `/api/admin/finance/summary` | Indicadores: ventas brutas, gastos, utilidad neta, pedidos por estado. |
| GET | `/api/admin/reviews` | Todas las resenas. |
| PATCH | `/api/admin/reviews/{id}/approve` | Aprobar resena (dispara recalculo de rating en Catalog). |
| DELETE | `/api/admin/reviews/{id}` | Rechazar / eliminar resena. |
| GET | `/api/admin/audit-logs` | Bitacora de transiciones de pedidos. |
| GET | `/health/commerce` | Salud del servicio. |

## 5. Payment Service - puerto 8005

Prefijo gateway: `/api/payments`.

Circuit Breaker Redis (threshold=5, open_ttl=60s, estados CLOSED/OPEN/HALF_OPEN) +
reintentos exponenciales (250ms, 500ms, 1s) en errores transitorios. Worker async
reconcilia PENDING/FAILED cada 5 min.

| Metodo | Endpoint | Descripcion | Rol |
|---|---|---|---|
| POST | `/api/payments` | Charge contra la pasarela mock. Body: `{"order_id":..., "amount":...}`. Pasa por CB. Devuelve `status` APPROVED/REJECTED/PENDING/FAILED. | Cliente/Admin |
| GET | `/api/payments/{payment_id}` | Detalle de pago. | Cliente/Admin |
| GET | `/api/payments/by-order/{order_id}` | Pago asociado a una orden. | Cliente/Admin |
| POST | `/api/payments/refund` | Refund de un pago (compensacion). | Admin |
| GET | `/api/payments/circuit/state` | Estado del Circuit Breaker (`CLOSED`/`OPEN`/`HALF_OPEN`, contador de fallos, TTL). | Admin |
| POST | `/api/payments/circuit/reset` | Reset manual del CB (uso operativo / runbook). | Admin |
| POST | `/api/payments/{payment_id}/reconcile` | Forzar reconciliacion de un pago. | Admin |
| GET | `/health/payment` | Salud del servicio. | Publico |

## Healthchecks consolidados

| Endpoint | Servicio | Verifica |
|---|---|---|
| GET `/health/gateway` | API Gateway | Nginx vivo |
| GET `/health/auth` | Auth | FastAPI + MySQL auth_db |
| GET `/health/catalog` | Catalog | FastAPI + MySQL catalog_db |
| GET `/health/inventory` | Inventory | FastAPI + MySQL inventory_db |
| GET `/health/commerce` | Commerce | FastAPI + MySQL commerce_db |
| GET `/health/payment` | Payment | FastAPI + MySQL payments_db |

## Codigos de estado relevantes

| Codigo | Significado en este sistema |
|---|---|
| 200/201 | Operacion exitosa. |
| 204 | Preflight CORS (gateway responde directo). |
| 401 | Sin token o token invalido. |
| 403 | Token valido pero rol insuficiente (ej. cliente intenta `/admin/...`). |
| 404 | Recurso no encontrado (incluye intentar leer pedidos de otro usuario). |
| 409 | Conflicto de estado: stock insuficiente, transicion invalida, lock contendido. |
| 422 | Body invalido (contrasena debil, campos faltantes, etc). |
| 429 | Rate limit (solo en `/api/auth/login`). |
| 503 | Circuit Breaker abierto en Payment (rechazo inmediato sin tocar pasarela). |
