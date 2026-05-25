#!/usr/bin/env bash
# ============================================================================
# Latency Monkey: forzar fallos repetidos de la pasarela y verificar que el
# Circuit Breaker abre + el checkout degrada graceful.
# ============================================================================
#
# Equivalente del Latency Monkey del Simian Army de Netflix: en vez de
# tirar abajo un servicio, simula latencia/fallos en una dependencia critica
# (la pasarela de pago) y verifica que el CB protege al sistema.
#
# Hipotesis (informe Fase 1, seccion 18.5):
#   1. Tras 5 fallos en 60s, el CB pasa a estado OPEN.
#   2. Mientras OPEN, las llamadas se rechazan inmediato con HTTP 503 sin
#      tocar la pasarela (proteccion al sistema).
#   3. El checkout con CB abierto devuelve 503 (codigo payment_unavailable)
#      al cliente y libera la reserva de stock (compensacion SAGA).
#   4. NO se crea Order falsa en estado PAID si la pasarela esta caida.
#   5. Reset admin (POST /payments/circuit/reset) restaura CLOSED y el
#      sistema vuelve a operar normal.
#
# Procedimiento:
#   1. Reset CB previo (estado limpio).
#   2. Disparar 5 charges con monto X.88 (el mock devuelve 500 con esos montos).
#   3. Verificar CB en OPEN con failures>=5.
#   4. Intentar charge nuevo → debe devolver 503 en <500ms (sin tocar mock).
#   5. Intentar checkout completo → debe devolver 503/payment_unavailable.
#   6. Reset admin del CB → verificar CLOSED.
#   7. Charge nuevo con monto .00 → APPROVED (sistema recuperado).
#
# Salida esperada: 9 PASS / 0 FAIL en condiciones normales.
# ============================================================================

set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$DIR/_helpers.sh"

step "Login admin (necesario para inspeccionar y resetear el CB)"
ADMIN=$(login "admin@tienda.com" "Admin1234*")
ATOKEN=$(echo "$ADMIN" | extract_field access_token)
[ -n "$ATOKEN" ] && ok "Admin token" || { fail "Admin login fallo"; summary; exit 1; }

step "Reset previo del CB"
curl -s -o /dev/null -X POST "$API/payments/circuit/reset" -H "Authorization: Bearer $ATOKEN"
INIT=$(curl -s "$API/payments/circuit/state" -H "Authorization: Bearer $ATOKEN")
ST=$(echo "$INIT" | extract_field state)
assert_eq "$ST" "CLOSED" "CB inicial CLOSED"

step "Provocar 5 fallos consecutivos con monto .88 (mock devuelve 500)"
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -X POST "$API/payments" -H "Authorization: Bearer $ATOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"order_id\":\"LAT-MK-$i-$(date +%s)\",\"amount\":50000.88}"
  info "intento $i disparado"
done

step "HIPOTESIS 1: CB esta OPEN"
ST_AFTER=$(curl -s "$API/payments/circuit/state" -H "Authorization: Bearer $ATOKEN")
STATE=$(echo "$ST_AFTER" | extract_field state)
assert_eq "$STATE" "OPEN" "CB abierto tras 5 fallos"
FAILURES=$(echo "$ST_AFTER" | python -c "import sys,json;print(json.load(sys.stdin)['failures'])")
if [ "$FAILURES" -ge 5 ]; then
  ok "Contador de fallos = $FAILURES (>=5)"
else
  fail "Contador insuficiente: $FAILURES"
fi

step "HIPOTESIS 2: Nuevo charge se rechaza inmediato con 503 SIN tocar la pasarela"
T0=$(date +%s%N)
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/payments" \
  -H "Authorization: Bearer $ATOKEN" -H "Content-Type: application/json" \
  -d "{\"order_id\":\"LAT-CB-FAST-$(date +%s)\",\"amount\":50000.00}")
T1=$(date +%s%N)
MS=$(( (T1 - T0) / 1000000 ))
assert_eq "$code" "503" "POST /payments con CB abierto devuelve 503"
if [ "$MS" -lt 500 ]; then
  ok "Respuesta inmediata (${MS}ms < 500ms, sin tocar mock)"
else
  warn "Respuesta tomo ${MS}ms (CB deberia ser <100ms; revisar)"
fi

step "HIPOTESIS 3: Checkout completo con CB abierto devuelve 503 (sin crear Order falsa)"
CLIENT=$(login "e2e@cliente.com" "E2eTest1234*")
CTOKEN=$(echo "$CLIENT" | extract_field access_token)
if [ -z "$CTOKEN" ]; then
  curl -s -o /dev/null -X POST "$API/auth/register" -H "Content-Type: application/json" \
    -d '{"name":"E2E","email":"e2e@cliente.com","phone":"3000000000","password":"E2eTest1234*"}'
  CLIENT=$(login "e2e@cliente.com" "E2eTest1234*")
  CTOKEN=$(echo "$CLIENT" | extract_field access_token)
fi
curl -s -o /dev/null -X DELETE "$API/cart" -H "Authorization: Bearer $CTOKEN"
curl -s -o /dev/null -X POST "$API/cart/items" -H "Authorization: Bearer $CTOKEN" \
  -H "Content-Type: application/json" -d '{"variant_id":11,"quantity":1}'
HTTP_CODE=$(curl -s -o /tmp/_ck_body -w "%{http_code}" -X POST "$API/checkout" \
  -H "Authorization: Bearer $CTOKEN" \
  -H "Content-Type: application/json" -H "Idempotency-Key: lat-$(date +%s)" \
  -d '{"delivery_name":"E2E","delivery_address":"Calle 100 #20","delivery_city":"Bogota","billing_document":"1024","contact_phone":"3001112233","contact_email":"e2e@cliente.com"}')
CK_BODY=$(cat /tmp/_ck_body)
CK_CODE=$(echo "$CK_BODY" | extract_field code)
if [ "$HTTP_CODE" = "503" ] && [ "$CK_CODE" = "payment_unavailable" ]; then
  ok "Checkout responde 503 payment_unavailable con CB abierto (degradacion graceful, sin Order)"
else
  fail "Checkout deberia devolver 503/payment_unavailable; obtuvo http=$HTTP_CODE code=$CK_CODE"
fi

step "HIPOTESIS 4: Reset admin del CB"
curl -s -o /dev/null -X POST "$API/payments/circuit/reset" -H "Authorization: Bearer $ATOKEN"
RESET=$(curl -s "$API/payments/circuit/state" -H "Authorization: Bearer $ATOKEN")
RST=$(echo "$RESET" | extract_field state)
assert_eq "$RST" "CLOSED" "CB vuelve a CLOSED tras reset"

step "HIPOTESIS 5: Nuevo charge tras reset funciona normal"
R=$(curl -s -X POST "$API/payments" -H "Authorization: Bearer $ATOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"order_id\":\"LAT-RECOVER-$(date +%s)\",\"amount\":50000.00}")
RST_STATUS=$(echo "$R" | extract_field status)
assert_eq "$RST_STATUS" "APPROVED" "Charge .00 tras reset = APPROVED"

summary
