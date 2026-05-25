# Revision de documentacion adjunta

Fecha de revision: 2026-05-22

Fuente revisada: `C:\Users\danie\Downloads\files1.zip`

Se contrastaron los 16 documentos DOCX del paquete contra el codigo actual del
proyecto, principalmente:

- `docker-compose.yml`
- `api-gateway/conf.d/gateway.conf`
- `services/*/app/api/*.py`
- `services/*/app/models/*.py`
- `services/*/app/services/*.py`
- `README.md`

## Resultado general

La documentacion es coherente con la arquitectura viva del proyecto:

- Los cinco microservicios estan correctamente identificados: Auth, Catalog,
  Inventory, Commerce y Payment.
- Los puertos 8001, 8002, 8003, 8004, 8005 y 9000 coinciden con
  `docker-compose.yml`.
- El flujo de checkout SAGA describe correctamente la secuencia
  `Inventory.reserve -> Payment.charge -> Inventory.confirm/release`.
- Los patrones descritos coinciden con el codigo: API Gateway, JWT compartido,
  Database per Service, Cache-Aside, locks Redis, `SELECT FOR UPDATE`, Circuit
  Breaker, reintentos, worker reconciler y correlation-id.
- Los estados logisticos del pedido coinciden con Commerce:
  `PAID`, `EN_PREPARACION`, `ENVIADO`, `ENTREGADO`, `CANCELADA`.
- La politica actual de resenas coincide con el codigo: se crean con
  `approved=False`, requieren aprobacion admin y luego Commerce actualiza
  `RatingSummary` en Catalog.
- La documentacion financiera coincide con el modelo actual: `OrderItem.unit_cost`
  es snapshot del costo usado para COGS historico.

## Ajustes recomendados en los DOCX

1. En `SRS_Tienda_Digital.docx` y `14_Despliegue_Docker.docx` se menciona
   "12 contenedores". El `docker-compose.yml` actual define 11 servicios:
   `mysql`, `phpmyadmin`, `redis`, `mailhog`, `api-gateway`, `auth-service`,
   `catalog-service`, `inventory-service`, `commerce-service`,
   `payment-service` y `payment-mock`.

2. En `02_CU01_CheckoutSAGA.docx` se indica que Payment devuelve `200 OK` con
   `status=APPROVED`. El endpoint actual `POST /payments` en Payment Service
   esta declarado con `status_code=201`, por lo que el texto deberia decir
   `201 Created` para ser exacto.

3. En `05_CU04_TransicionLogistica.docx` se dice que Commerce devuelve "la nueva
   version del pedido". El endpoint actual `PATCH /admin/orders/{id}/status`
   devuelve un resumen `{order_id, status, message}`. La idea funcional es
   correcta, pero el texto puede ajustarse a "devuelve confirmacion con el nuevo
   estado".

## Documentos revisados

- `SRS_Tienda_Digital.docx`
- `Manual_Usuario_Tienda_Digital.docx`
- `01_CasosDeUso_General.docx`
- `02_CU01_CheckoutSAGA.docx`
- `03_CU02_ResenaProducto.docx`
- `04_CU03_VariantesNike.docx`
- `05_CU04_TransicionLogistica.docx`
- `06_CU05_DashboardFinanciero.docx`
- `07_Secuencia_CheckoutSAGA.docx`
- `08_Secuencia_AprobacionResena.docx`
- `09_Actividad_FlujoCompra.docx`
- `10_Estado_CicloVidaPedido.docx`
- `11_Estado_CicloVidaResena.docx`
- `12_Clases_Dominio.docx`
- `13_Componentes_Microservicios.docx`
- `14_Despliegue_Docker.docx`
