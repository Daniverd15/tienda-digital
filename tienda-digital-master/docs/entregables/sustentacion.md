# Guía de Sustentación — Fase 2 Tienda Digital
## Preguntas técnicas anticipadas y respuestas basadas en el código

---

## Cómo usar este documento

Para cada pregunta: leer la respuesta, identificar el archivo de evidencia y estar preparado para mostrar ese código en pantalla. Las respuestas están redactadas para ser dichas en voz alta, no para leer textualmente.

---

## Bloque 1: Arquitectura General

**P1: ¿Por qué eligieron 5 microservicios en lugar de más o menos?**

R: El informe de Fase 1 propuso una descomposición por Bounded Context según el dominio del negocio. Identidad es Auth, el catálogo que ven los clientes es Catalog, el control de stock es Inventory, el flujo de compra completo es Commerce y los pagos son Payment. Cinco servicios cubren los subdominios sin sobre-fragmentar (no hay un servicio por entidad, sino por contexto de negocio). Con menos servicios habría acoplamiento entre dominios; con más, complejidad operativa sin beneficio funcional.

*Evidencia: `docs/arquitectura.md` sección "Bounded contexts".*

---

**P2: ¿Qué pasa si levantan `docker compose up` y uno de los servicios falla al arrancar?**

R: Cada microservicio tiene un `HEALTHCHECK` Docker y `depends_on` con `condition: service_healthy` o `service_started`. El gateway tiene `service_healthy` para los 5 servicios, lo que significa que el gateway no empieza a servir tráfico hasta que todos los servicios pasen su healthcheck. Si un servicio falla repetidamente, Docker lo marca como `unhealthy` y el gateway nunca arrancaría. Los servicios también tienen `restart: unless-stopped`, así que Docker los reinicia automáticamente en caso de crash.

*Evidencia: `docker-compose.yml` líneas 84-96 (api-gateway depends_on).*

---

**P3: ¿Cómo se comunican los microservicios entre sí?**

R: Por dos mecanismos. El primero es llamadas REST HTTP síncronas — Commerce llama a Inventory y Payment durante el checkout (SAGA). Catalog llama a Inventory para enriquecer el detalle de producto con variantes y stock. Todas estas llamadas usan el nombre de contenedor Docker como host (por ejemplo `http://inventory-service:8003`), que Docker resuelve internamente en la red `tienda_net`. El segundo mecanismo es Redis: Catalog escribe y lee el cache, Inventory usa Redis para locks distribuidos, Payment usa Redis para los contadores del Circuit Breaker.

*Evidencia: `commerce-service/app/services/http_clients.py`, `catalog-service/app/services/inventory_client.py`.*

---

## Bloque 2: Patrones

**P4: Expliquen el patrón Database per Service. ¿Están usando realmente una base de datos por servicio?**

R: Sí, aunque en variante lógica. Tenemos un solo servidor MySQL pero con 5 schemas separados: `auth_db`, `catalog_db`, `inventory_db`, `commerce_db`, `payments_db`. Lo clave es que hay 5 usuarios MySQL distintos, cada uno con `GRANT` exclusivo solo sobre su schema. El usuario `auth_user` no puede hacer un `SELECT` en `catalog_db` — MySQL lo rechaza con acceso denegado. Esto lo verificamos con el Conformity Monkey que intenta accesos cruzados y verifica que fallan. En producción, cada schema puede migrarse a su propia instancia sin cambiar el código — solo cambia `DATABASE_URL` en el `.env`.

*Evidencia: `database-init/02_create_users.sql`, `scripts/chaos/conformity_monkey.sh`.*

---

**P5: ¿Cómo funciona el Cache-Aside en Catalog? ¿Qué pasa si Redis se cae?**

R: El flujo es: cuando llega un GET de productos, primero consultamos la clave en Redis. Si existe (cache hit), devolvemos el JSON cacheado. Si no existe (cache miss), hacemos la query a MySQL, guardamos el resultado en Redis con TTL y devolvemos. Cuando un admin edita un producto, borramos todas las claves que empiecen con `catalog:products:` — eso fuerza que el próximo GET lea desde MySQL y actualice el cache. Si Redis no está disponible, capturamos la excepción y simplemente servimos desde MySQL. El cliente no ve ninguna diferencia, solo que las respuestas son un poco más lentas.

*Evidencia: `catalog-service/app/core/cache.py`.*

---

**P6: ¿Qué es exactamente el Circuit Breaker y cómo lo implementaron?**

R: Es un patrón de resiliencia que evita que los fallos en la pasarela de pago se propaguen al sistema. Funciona como un fusible eléctrico con 3 estados. En CLOSED (normal), los pagos pasan al mock. Cada vez que el mock responde con error, incrementamos un contador en Redis con TTL de 60 segundos. Cuando ese contador llega a 5, seteamos una clave `cb:gateway:open` en Redis con TTL de 60s — eso abre el circuito (estado OPEN). Mientras está OPEN, rechazamos los pagos inmediatamente con HTTP 503 sin siquiera contactar la pasarela, lo que tarda menos de 100ms en lugar de esperar el timeout. Después de 60 segundos, la clave expira y permitimos una llamada de prueba (HALF_OPEN). Si tiene éxito, borramos todos los contadores y volvemos a CLOSED. Si falla, volvemos a abrir por otros 60 segundos.

*Evidencia: `payment-service/app/core/circuit_breaker.py` — clase `CircuitBreaker`, métodos `allow()`, `record_failure()`, `record_success()`.*

---

**P7: Expliquen la SAGA. ¿Qué pasa si el pago es aprobado pero falla la confirmación de inventario?**

R: La SAGA tiene exactamente ese caso documentado. Cuando el pago es APPROVED, llamamos a Inventory para confirmar (decrementar stock real). Si esa confirmada falla (servicio momentáneamente no disponible), la Order ya está creada con estado PAID — el pago ya se cobró. En ese caso, la Order queda en estado PAID en commerce_db pero el stock no bajó en inventory_db. No hacemos rollback del pago porque ya se procesó en la pasarela. En cambio, registramos un `OrderAuditLog` con la inconsistencia para que un administrador lo revise, y el scheduler de Inventory eventualmente libera la reserva al expirar el TTL. En el informe de Fase 1 identificamos esto como la limitación del MVP donde el Outbox Pattern resolvería el problema. Para los casos que sí controlamos — Inventory caído antes del pago, pago rechazado, Circuit Breaker abierto — la compensación sí es automática: llamamos a `POST /inventory/release` y el carrito queda intacto.

*Evidencia: `commerce-service/app/services/checkout_saga.py` — línea ~424, comentario "caso raro: Order queda PAID + audit".*

---

**P8: ¿Qué es el Distributed Lock y por qué lo necesitan?**

R: Cuando dos usuarios intentan comprar el último producto al mismo tiempo, sin lock distribuido ambos podrían leer `stock=1`, proceder con la compra y terminar con `stock=-1`. El lock distribuido en Redis usa el comando `SET NX EX`: "set este valor, pero solo si no existe (NX), con un tiempo de expiración (EX)". El proceso que logra el SET adquiere el lock. El otro intento obtiene "no adquirido" y lanza 409 de inmediato. Para liberar, usamos un script Lua que verifica que quien libera es el mismo que adquirió (por un token aleatorio). Eso evita que el proceso A libere accidentalmente el lock del proceso B. Si Redis no está disponible, caemos a `SELECT FOR UPDATE` en MySQL, que tiene semántica equivalente pero solo local a MySQL.

*Evidencia: `inventory-service/app/core/redis_lock.py`.*

---

**P9: ¿Qué es el SSO con JWT compartido? ¿No es un riesgo de seguridad?**

R: En lugar de que cada microservicio llame al Auth Service para validar cada token (lo que crearía acoplamiento y un cuello de botella), todos los servicios comparten el mismo `JWT_SECRET` y validan el token localmente usando PyJWT. El token incluye `sub` (user_id), `role` y `email` en el payload, así que cada servicio sabe quién es el usuario sin preguntar. El riesgo es que si alguien obtiene el `JWT_SECRET`, puede forjar tokens. Lo mitigamos con varias capas: el secreto nunca está en el código (viene de variable de entorno), los tokens tienen expiración de 60 minutos, los refresh tokens se almacenan hasheados en BD y se rotan en cada uso. Para producción, el secreto debería estar en un sistema de gestión de secretos (AWS Secrets Manager, Vault). Para el MVP académico, la variable de entorno es el enfoque correcto.

*Evidencia: `services/auth-service/app/core/security.py` + `docker-compose.yml` variable `JWT_SECRET`.*

---

## Bloque 3: Chaos Engineering

**P10: ¿Cómo ejecutan los tests de Chaos Engineering y qué demuestran?**

R: Tenemos 5 scripts ejecutables. Para ejecutarlos primero levantamos todo con `docker compose up -d` y luego corremos por ejemplo `bash scripts/chaos/latency_monkey_payment.sh`. Los scripts usan curl para hacer requests al sistema y verifican los códigos HTTP y cuerpos de respuesta. El Latency Monkey, por ejemplo, dispara 5 pagos con monto terminado en `.88` (que el mock siempre responde con error 500), luego verifica que el Circuit Breaker esté en OPEN, luego intenta un checkout completo y verifica que devuelve 503 sin haber creado ninguna Order, y finalmente resetea el CB y verifica que todo vuelve a funcionar normal. Son 9 assertions en 9 pasos documentados — si todas pasan, demostramos que la protección funciona.

*Evidencia: `scripts/chaos/latency_monkey_payment.sh`.*

---

**P11: ¿Por qué su Conformity Monkey tiene 51 verificaciones?**

R: Verificamos 5 categorías por cada uno de los 5 servicios, más pruebas de aislamiento de base de datos. Cada servicio debe tener: Dockerfile, requirements.txt, .env.example, app/main.py (20 checks), el Dockerfile debe declarar USER no-root (5 checks), debe responder en su puerto propio con su nombre correcto (5 checks), el gateway debe enrutar correctamente hacia él (5 checks). Eso da 35. Los 16 restantes son verificaciones de que los usuarios MySQL de un servicio no pueden acceder al schema de otro — intentamos queries cruzadas y verificamos que MySQL las rechaza. En total, 51 verificaciones de conformidad arquitectural.

*Evidencia: `scripts/chaos/conformity_monkey.sh`.*

---

**P12: ¿Qué es el Correlation ID y para qué sirve en su sistema?**

R: Es un identificador único (UUID) que el gateway Nginx genera para cada request entrante. Lo propaga como header `X-Correlation-Id` al microservicio destino. Ese servicio, a su vez, lo incluye en sus logs y en las tablas de auditoría (`OrderAuditLog`, `AccessLog`, `FailedCheckoutAttempt`). Si un checkout falla y el usuario reporta el problema, el administrador puede tomar ese correlation_id y rastrear exactamente qué pasó en cada servicio: cuándo llegó al gateway, cuándo llegó a Commerce, si se llamó a Inventory, si se intentó el pago, etc. Sin correlation ID, los logs de 5 servicios son imposibles de correlacionar.

*Evidencia: `api-gateway/conf.d/gateway.conf` (generación), `commerce-service/app/services/checkout_saga.py` (propagación).*

---

## Bloque 4: Preguntas de decisión técnica

**P13: ¿Por qué no implementaron RabbitMQ si estaba en el diseño de Fase 1?**

R: El informe de Fase 1 plantea tres niveles de alcance. El Nivel 1 (MVP) incluye los 5 microservicios, Docker, JWT y health checks. El Nivel 2 agrega Cache-Aside, locks distribuidos, SAGA y Circuit Breaker. El Nivel 3 agrega RabbitMQ, Outbox Pattern y DLQ. Implementamos completo el Nivel 1 y el Nivel 2. El Nivel 3 se descartó conscientemente porque requeriría al menos 3 contenedores adicionales (RabbitMQ + workers), una implementación de Outbox Pattern y un sistema de Dead Letter Queue, triplicando la complejidad de infraestructura sin agregar valor funcional demostrable para el MVP. La SAGA síncrona cubre el caso de uso de checkout correctamente para este contexto académico.

*Evidencia: `docs/arquitectura.md` sección "Decisiones de migración".*

---

**P14: ¿Cómo garantizan que el frontend funciona con la nueva arquitectura?**

R: El frontend React solo necesita cambiar la URL base de `http://localhost:8000` (monolito) a `http://localhost/api` (gateway). Internamente, la SPA hace las mismas llamadas HTTP y recibe los mismos contratos JSON. El gateway se encarga de rutear. En el Bloque 7 de la migración (documentado en `docs/fase2.md`) se ajustaron algunas rutas que cambiaron entre el monolito y los microservicios — por ejemplo, `/orders/my` pasó a ser `/orders/mine`, `/admin/dashboard` pasó a `/admin/finance/summary`. También se adaptó el componente `Badge.jsx` para soportar tanto los estados en MAYÚSCULAS de los microservicios como los estados en minúsculas del monolito legacy.

*Evidencia: `docs/fase2.md` Bloque 7, `frontend/src/api/client.js`.*

---

**P15: Si tuvieran que desplegar esto en producción, ¿qué cambiarían?**

R: Varias cosas. Primero, el `JWT_SECRET` en producción iría en un gestor de secretos (AWS Secrets Manager, HashiCorp Vault), no en variables de entorno en texto plano. Segundo, Redis necesitaría autenticación con `requirepass`. Tercero, MySQL tendría contraseñas fuertes en lugar de `auth_pass`, `catalog_pass`, etc. Cuarto, el gateway necesitaría TLS/HTTPS — agregar un certificado y forzar redirect HTTP→HTTPS. Quinto, cada servicio podría desplegarse independientemente en su propio contenedor o pod Kubernetes, y los healthchecks ya son compatibles con Kubernetes (responden JSON con status ok). Sexto, el payment-mock se reemplazaría por la integración real con la pasarela (Stripe, PayU, etc.) — solo cambia `PAYMENT_MOCK_URL` en el `.env` del payment-service.

*Evidencia: `docs/arquitectura.md` sección "Preparación para producción".*

---

## Bloque 5: Preguntas trampa / difíciles

**P16: ¿Cómo manejan la consistencia eventual entre servicios?**

R: En nuestra implementación la consistencia es inmediata en el happy path porque la SAGA es síncrona. Cada paso espera la respuesta del anterior. El caso de consistencia eventual real surge cuando el commit de Commerce falla después de que Inventory ya confirmó el stock — ahí hay una ventana de inconsistencia. La manejamos con dos mecanismos: el OrderAuditLog registra el evento con correlation_id para auditoría manual, y el scheduler de Inventory libera automáticamente las reservas vencidas (15 minutos TTL), lo que eventualmente devuelve el stock. En un sistema de producción, el Outbox Pattern eliminaría esa ventana al hacer la confirmación de Inventory y el commit de Commerce en la misma transacción distribuida usando eventos en una tabla de outbox.

---

**P17: ¿Un microservicio puede llamar directamente a la base de datos de otro?**

R: No. El aislamiento es doble. A nivel de arquitectura: ningún microservicio conoce el `DATABASE_URL` de otro — cada uno solo tiene acceso a su propia base configurada en `docker-compose.yml`. A nivel de base de datos: el usuario MySQL de cada servicio solo tiene `GRANT` en su schema. Si por algún error de configuración `catalog-service` intentara conectarse a `auth_db`, MySQL rechazaría la conexión. Esto lo demostramos con el Conformity Monkey que realiza exactamente esa prueba. La única forma de acceder a datos de otro servicio es a través de su API HTTP — por ejemplo, Catalog llama a `GET /inventory/variants/{id}` para obtener stock, no accede directamente a `inventory_db`.

---

**P18: ¿Por qué el Commerce Service usa `service_started` en lugar de `service_healthy` para Inventory y Payment?**

R: Porque Commerce puede inicializar aunque Inventory y Payment aún no estén listos. Los microservicios no se llaman en el arranque; solo se llaman cuando un usuario ejecuta un checkout. El tiempo de arranque de Commerce es de unos 10 segundos, y para cuando el primer usuario intente un checkout, Inventory y Payment ya estarán healthy. Si usáramos `service_healthy`, el tiempo total de arranque aumentaría porque Commerce esperaría a que todos los servicios pasen sus retries de healthcheck. La resiliencia real viene de los reintentos en las llamadas HTTP — si Inventory no responde, Commerce devuelve 503 al cliente con un mensaje claro y registra el intento fallido.

*Evidencia: `docker-compose.yml` línea 192-193.*

---

**P19: ¿Cómo demuestran el rate limiting en vivo?**

R: Enviamos 6 requests de login en rápida sucesión al mismo endpoint:
```bash
for i in {1..6}; do
  curl -s -o /dev/null -w "intento $i: %{http_code}\n" \
    -X POST http://localhost/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@tienda.com","password":"wrongpass"}'
done
```
Los primeros 5 devuelven 401 (credenciales incorrectas — el endpoint los procesa). El sexto devuelve 429 (Too Many Requests) — Nginx lo rechaza antes de que llegue al servicio. El Security Monkey tiene exactamente esta prueba en sus 27 assertions.

*Evidencia: `api-gateway/nginx.conf` zona `auth_limit`, `scripts/chaos/security_monkey.sh`.*

---

**P20: ¿Qué es el Idempotency-Key y cómo lo usan?**

R: Es un header que el cliente envía en `POST /checkout`. Si el cliente envía el mismo checkout dos veces (por doble-click, pérdida de conexión o retry del frontend), el segundo request devuelve la Order que ya existe en lugar de ejecutar la SAGA de nuevo — lo que evitaría cobrar dos veces al cliente. El valor debe ser único por intento (típicamente un UUID que el frontend genera). En los tests E2E usamos `Idempotency-Key: e2e-$(date +%s)` para asegurar que cada ejecución del script tenga un key distinto.

*Evidencia: `commerce-service/app/api/checkout.py`, `scripts/e2e/flujo_completo.sh` línea 117.*

---

## Checklist de demostración en vivo

Secuencia recomendada para la sustentación:

```bash
# 1. Mostrar los contenedores corriendo
docker compose ps

# 2. Healthchecks
for s in gateway auth catalog inventory commerce payment; do
  echo -n "$s: "; curl -s "http://localhost/health/$s" | python -c "import sys,json;d=json.load(sys.stdin);print(d['status'])"
done

# 3. Registrar un usuario nuevo
curl -s -X POST http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo","email":"demo@prueba.com","phone":"3001234567","password":"Demo1234*"}'

# 4. Login y guardar token
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@tienda.com","password":"Admin1234*"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
echo "Token: ${TOKEN:0:50}..."

# 5. Catálogo (Cache-Aside)
curl -s http://localhost/api/products | python -m json.tool | head -30

# 6. Estado del Circuit Breaker
curl -s http://localhost/api/payments/circuit/state \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# 7. Abrir CB con 5 fallos
for i in 1 2 3 4 5; do
  curl -s -X POST http://localhost/api/payments \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"order_id\":\"demo-$i\",\"amount\":100.88}" > /dev/null
  echo "Fallo $i disparado"
done
curl -s http://localhost/api/payments/circuit/state \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;d=json.load(sys.stdin);print('CB State:', d['state'], '| Failures:', d['failures'])"

# 8. Resetear CB
curl -s -X POST http://localhost/api/payments/circuit/reset \
  -H "Authorization: Bearer $TOKEN"

# 9. Mostrar schemas MySQL en phpMyAdmin
# http://localhost:8080 → servidor: mysql, usuario: root, contraseña: root_password

# 10. Mailhog (correos transaccionales)
# http://localhost:8025
```

---

## Frases clave para la sustentación

- *"La SAGA orquestada síncrona garantiza que nunca se cobra al cliente si no hay stock, y nunca se descuenta stock si el pago no fue aprobado."*
- *"El Circuit Breaker protege al sistema de esperar timeouts innecesarios cuando la pasarela ya sabemos que está caída."*
- *"El Conformity Monkey verifica que el aislamiento de datos es real — un usuario MySQL no puede cruzar al schema de otro servicio."*
- *"El monolito legacy está preservado en `backend_legacy_monolito/` como evidencia del punto de partida de la migración."*
- *"133 verificaciones automatizadas — no hay un solo claim sobre el sistema que no esté respaldado por código ejecutable."*
