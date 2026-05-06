# Backlog Y Commits

## Evidencia Git

```text
67e88c9 (HEAD -> master) chore(RNF-03): usabilidad mantenibilidad respaldo trazabilidad y observabilidad
7d5f9f7 security(RNF-02): seguridad privacidad e integridad transaccional
8df2a52 perf(RNF-01): monitoreo rendimiento disponibilidad y concurrencia
0358ddb chore: esquema mysql y datos iniciales de prueba
ca0d38f feat(RF-09): interfaces de configuracion mensajes y resenas
dcf87dd fix(RF-09): exponer productos en pedidos para resenas
431d7aa feat(RF-09): configuracion de tienda mensajes parametros y resenas
f2c2ff8 feat(RF-08): dashboard financiero y vistas administrativas
4411459 feat(RF-08): gestion administrativa financiera y reportes
523fabd feat(RF-07): panel administrativo de catalogo e inventario
3a52bb9 feat(RF-07): administracion de catalogo variantes e inventario
62cbeba feat(RF-06): vistas de pedidos notificaciones y gestion admin
9a5c20b feat(RF-06): historial estados y actualizacion de pedidos
9eb3372 feat(RF-05): resumen de pago y resultado de transaccion
f2b455b feat(RF-05): calculo de compra pagos simulados y creacion de pedidos
a330830 feat(RF-04): carrito checkout y captura de datos
a040275 feat(RF-04): servicios de carrito y validacion de stock
45e7377 feat(RF-03): busqueda filtros y detalle de productos
8089b08 feat(RF-03): api de busqueda filtros variantes y valoraciones
f2260fc feat(RF-02): tienda digital con identidad visual y catalogo activo
ac6f538 feat(RF-02): endpoints publicos de tienda categorias y productos
c1e3523 feat(RF-01): interfaces de login registro y sesion
4851e2b feat(RF-01): gestion de cuentas autenticacion y roles
9332239 chore: estructura inicial del proyecto y configuracion local
```

## Requisitos

| Req | Titulo | Criterio de aceptacion resumido | Tasks | Responsable | Commits |
|---|---|---|---|---|---|
| RF-01 | El sistema debe permitir la gestion de cuentas, autenticacion y control de acceso de clientes y administradores. | Crear cuentas, iniciar/cerrar sesion, perfil admin y roles. | Registro; login/logout; roles; perfil admin; seguridad credenciales. | Santiago/Daniel | `4851e2b`, `c1e3523` |
| RF-02 | El sistema debe mostrar la tienda digital, categorias y productos activos con identidad visual propia de la empresa. | Mostrar logo/colores/mensajes/categorias/productos publicados. | Home; identidad; categorias; productos; publicado. | Daniel/Santiago | `ac6f538`, `f2260fc` |
| RF-03 | El sistema debe permitir buscar, filtrar y consultar el detalle de productos con sus variantes. | Buscar, filtrar, ficha completa, variantes, stock y promedio. | Buscador; filtros; ficha; variantes; validacion seleccion. | Daniel/Santiago | `8089b08`, `45e7377` |
| RF-04 | El sistema debe permitir gestionar el carrito de compras, validar stock y capturar datos para finalizar el pedido. | Agregar, modificar, eliminar, validar stock y checkout. | Carrito; cantidades; eliminar; stock; datos checkout. | Daniel/Santiago | `a040275`, `a330830` |
| RF-05 | El sistema debe calcular valores de compra, integrar pasarela de pago y crear pedidos con estado actualizado. | Calculo, pago simulado, pedido unico y estado por pago. | Valores; resumen; pasarela; pedido; respuesta pago. | Santiago/Daniel | `f2b455b`, `9eb3372` |
| RF-06 | El sistema debe permitir consultar, actualizar y notificar el estado de los pedidos. | Historial, detalle, estados, actualizacion admin y notificaciones. | Historial; detalle; estados; admin; notificar. | Santiago/Daniel | `9a5c20b`, `62cbeba` |
| RF-07 | El sistema debe permitir la gestion administrativa de categorias, productos, variantes e inventario. | CRUD catalogo, variantes, SKU, costos, precios, movimientos y alertas. | Categorias; productos; comercial; variantes; inventario. | Santiago/Daniel | `3a52bb9`, `523fabd` |
| RF-08 | El sistema debe permitir gestionar informacion administrativa, financiera y reportes del negocio. | Empleados, gastos, indicadores, dashboard y reportes. | Empleados; gastos; indicadores; dashboard; exportar. | Santiago/Daniel | `4411459`, `f2c2ff8` |
| RF-09 | El sistema debe permitir la configuracion general de la tienda, mensajes informativos, parametros globales y resenas de productos. | Configurar tienda, mensajes, parametros y resenas con compra entregada. | Configuracion; mensajes; parametros; resenas; compra entregada. | Santiago/Daniel | `431d7aa`, `dcf87dd`, `ca0d38f` |
| RNF-01 | El sistema debe garantizar rendimiento, disponibilidad y capacidad concurrente bajo carga normal. | Respuesta adecuada, concurrencia y salud. | Tiempos; concurrencia cliente/admin; disponibilidad; optimizar. | Tomas | `8df2a52` |
| RNF-02 | El sistema debe garantizar seguridad, privacidad e integridad de la informacion y las transacciones. | HTTPS preparado, sesiones seguras, roles, minimo privilegio e integridad. | TLS; contrasenas; admin; privilegio; transacciones. | Tomas | `7d5f9f7` |
| RNF-03 | El sistema debe garantizar usabilidad, compatibilidad, mantenibilidad, respaldo, trazabilidad y observabilidad. | Accesibilidad, multidispositivo, arquitectura, backup y logs. | Usabilidad; responsive; arquitectura; respaldo; observabilidad. | Tomas | `67e88c9` |

