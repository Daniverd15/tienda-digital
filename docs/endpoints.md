# Endpoints

Todos los cuerpos son JSON salvo los reportes. Rutas admin requieren JWT con rol `admin`; rutas cliente requieren JWT.

| Metodo | Endpoint | Descripcion | Rol | Request ejemplo | Response ejemplo |
|---|---|---|---|---|---|
| POST | `/auth/register` | Registro cliente | Publico | `{"name":"Ana","email":"ana@mail.com","password":"Cliente123*"}` | `{"access_token":"...","user":{"role":"customer"}}` |
| POST | `/auth/login` | Inicio de sesion | Publico | `{"email":"admin@tienda.com","password":"Admin123*"}` | `{"access_token":"...","user":{"role":"admin"}}` |
| POST | `/auth/logout` | Cierre local registrado | Cliente/Admin | `{}` | `{"message":"Sesion cerrada en el cliente."}` |
| GET | `/auth/me` | Usuario actual | Cliente/Admin | `{}` | `{"id":1,"email":"admin@tienda.com"}` |
| PUT | `/admin/profile` | Perfil admin | Admin | `{"name":"Admin"}` | `{"role":"admin"}` |
| GET | `/store/settings` | Configuracion visible | Publico | `{}` | `{"commercial_name":"Distrito Urbano"}` |
| GET | `/store/messages` | Mensajes activos | Publico | `{}` | `[{"title":"Envio local"}]` |
| GET | `/categories` | Categorias activas | Publico | `{}` | `[{"name":"Ropa"}]` |
| GET | `/products` | Productos activos | Publico | `{}` | `[{"name":"Camiseta basica"}]` |
| GET | `/products/search?q=tenis` | Buscar y filtrar | Publico | `{}` | `[{"name":"Tenis deportivos"}]` |
| GET | `/products/{id}` | Detalle producto | Publico | `{}` | `{"variants":[{"sku":"TEN-40"}]}` |
| GET | `/products/{id}/reviews` | Resenas aprobadas | Publico | `{}` | `[{"rating":5}]` |
| GET | `/cart` | Carrito abierto | Cliente | `{}` | `{"items":[],"subtotal":0}` |
| POST | `/cart/items` | Agregar item | Cliente | `{"variant_id":1,"quantity":1}` | `{"items":[...]}` |
| PUT | `/cart/items/{id}` | Cambiar cantidad | Cliente | `{"quantity":2}` | `{"subtotal":90000}` |
| DELETE | `/cart/items/{id}` | Eliminar item | Cliente | `{}` | `{"message":"Item eliminado del carrito."}` |
| POST | `/cart/validate-stock` | Validar stock | Cliente | `{}` | `{"valid":true}` |
| POST | `/checkout` | Calcular compra | Cliente | `{"delivery_name":"Ana",...}` | `{"subtotal":45000,"total":52000}` |
| POST | `/payments/simulate` | Pago simulado | Cliente | `{"amount":52000,"requested_status":"aprobado"}` | `{"status":"aprobado"}` |
| POST | `/orders` | Crear pedido | Cliente | `{"payment_status":"aprobado",...}` | `{"order_code":"TD-..."}` |
| GET | `/orders/my` | Historial cliente | Cliente | `{}` | `[{"status":"entregado"}]` |
| GET | `/orders/{id}` | Detalle pedido propio/admin | Cliente/Admin | `{}` | `{"items":[...]}` |
| GET | `/notifications` | Notificaciones | Cliente | `{}` | `[{"read":false}]` |
| PUT | `/notifications/{id}/read` | Marcar leida | Cliente | `{}` | `{"message":"Notificacion marcada como leida."}` |
| GET | `/admin/orders` | Pedidos admin | Admin | `{}` | `[{"order_code":"TD-..."}]` |
| PUT | `/admin/orders/{id}/status` | Actualizar estado | Admin | `{"status":"entregado"}` | `{"status":"entregado"}` |
| GET/POST | `/admin/categories` | Listar/crear categoria | Admin | `{"name":"Ropa"}` | `{"id":1}` |
| GET/PUT/DELETE | `/admin/categories/{id}` | Ver/editar/archivar | Admin | `{"active":false}` | `{"message":"Categoria archivada."}` |
| GET/POST | `/admin/products` | Listar/crear producto | Admin | `{"name":"Producto"}` | `{"id":1}` |
| GET/PUT/DELETE | `/admin/products/{id}` | Ver/editar/archivar | Admin | `{...}` | `{"published":true}` |
| GET/POST | `/admin/products/{id}/variants` | Listar/crear variante | Admin | `{"sku":"SKU"}` | `{"sku":"SKU"}` |
| PUT/DELETE | `/admin/products/{id}/variants/{variant_id}` | Editar/desactivar variante | Admin | `{...}` | `{"active":false}` |
| POST | `/admin/inventory/movements` | Movimiento inventario | Admin | `{"variant_id":1,"movement_type":"entrada","quantity":5,"reason":"Compra"}` | `{"quantity":5}` |
| GET | `/admin/inventory/alerts` | Alertas stock | Admin | `{}` | `[{"stock":3}]` |
| GET | `/admin/customers` | Clientes | Admin | `{}` | `[{"email":"cliente@tienda.com"}]` |
| GET | `/admin/customers/{id}/orders` | Pedidos de cliente | Admin | `{}` | `[{"order_code":"TD-..."}]` |
| CRUD | `/admin/employees` | Empleados | Admin | `{"name":"Auxiliar"}` | `{"employment_status":"active"}` |
| CRUD | `/admin/expenses` | Gastos | Admin | `{"amount":500000}` | `{"expense_type":"Publicidad"}` |
| GET | `/admin/finance/summary` | Indicadores | Admin | `{}` | `{"utilidad_neta":0}` |
| GET | `/admin/dashboard` | Dashboard | Admin | `{}` | `{"ventas_brutas":52000}` |
| GET | `/admin/reports/export/csv` | Export CSV | Admin | `{}` | `text/csv` |
| GET | `/admin/reports/export/pdf` | HTML imprimible | Admin | `{}` | `text/html` |
| GET/PUT | `/admin/settings` | Config tienda | Admin | `{"commercial_name":"..."}` | `{"currency":"COP"}` |
| CRUD | `/admin/messages` | Mensajes | Admin | `{"title":"Promo"}` | `{"active":true}` |
| GET | `/admin/audit-logs` | Bitacora | Admin | `{}` | `[{"action":"login"}]` |
| POST | `/reviews` | Crear resena validada | Cliente | `{"product_id":1,"order_id":1,"rating":5}` | `{"approved":true}` |
| GET | `/health` | Salud API/DB | Publico | `{}` | `{"status":"ok"}` |

