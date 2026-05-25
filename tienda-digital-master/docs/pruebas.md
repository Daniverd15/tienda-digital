# Pruebas

## Pruebas Automatizadas

```powershell
cd backend
pytest
```

Casos incluidos:

- Hash seed PBKDF2 verifica `Cliente123*` y rechaza contrasena incorrecta.
- Politica de contrasenas rechaza claves debiles.
- JWT conserva sujeto y rol.
- Calculo de checkout no permite total negativo.
- Calculo de checkout aplica subtotal, costos adicionales y descuento.

## Casos Positivos Manuales

- Login admin con `admin@tienda.com / Admin123*`.
- Login cliente con `cliente@tienda.com / Cliente123*`.
- Catalogo lista categorias y productos publicados.
- Busqueda por texto y filtros de precio/stock.
- Detalle muestra variantes y resenas.
- Cliente agrega producto con stock al carrito.
- Cliente modifica cantidad y elimina item.
- Checkout calcula total y permite pago aprobado, rechazado o pendiente.
- Pago aprobado crea pedido y descuenta inventario.
- Admin actualiza pedido a enviado/entregado si el pago esta aprobado.
- Admin crea categorias, productos, variantes y movimientos.
- Admin ve alertas de stock, empleados, gastos, dashboard y reportes.
- Cliente crea resena solo desde pedido entregado.

## Casos Negativos

- Cliente no accede a rutas `/admin`.
- Usuario no ve pedidos de otro usuario.
- Stock insuficiente bloquea carrito/checkout.
- Pedido no avanza a preparacion/enviado/entregado si el pago no esta aprobado.
- Resena rechazada si el pedido no esta entregado o el producto no fue comprado.
- Movimiento de salida rechaza stock negativo.

## RNF

- `/health` valida disponibilidad API/DB.
- `X-Response-Time-ms` expone tiempo de respuesta.
- `system_logs` registra solicitudes.
- `audit_logs` registra login, registro, carrito, pedido, inventario, configuracion y resenas.
- CSS responsive y `:focus-visible` mejoran compatibilidad y accesibilidad.
- `database/backup_mysql.ps1` cubre respaldo local.

## Limitacion Del Entorno De Generacion

En esta maquina no estaban disponibles Python ni Docker, por lo que no se pudo ejecutar `pytest`, `uvicorn` ni `docker compose`. El proyecto queda listo para correr esos comandos cuando las herramientas esten instaladas.

