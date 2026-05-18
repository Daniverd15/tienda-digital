#!/usr/bin/env bash
# Chaos Monkey: detener Inventory durante un checkout activo.
#
# Hipotesis (informe Fase 1, seccion 18.4):
# - El catalogo sigue respondiendo (modo degradado)
# - El checkout que requiere Inventory falla controlado con 4xx/5xx
#   y la orden queda en SIN_STOCK / PAGO_PENDIENTE, NO en PAID falso
# - Al restaurar Inventory, el sistema vuelve a operar normal
#
# Uso:
#   ./scripts/chaos/chaos_monkey_inventory.sh

set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$DIR/_helpers.sh"

step "Pre-condicion: Inventory healthy"
code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost/health/inventory")
assert_eq "$code" "200" "Inventory esta healthy antes del experimento"

step "Cliente para el experimento"
CLIENT=$(login "e2e@cliente.com" "E2eTest1234*")
TOKEN=$(echo "$CLIENT" | extract_field access_token)
if [ -z "$TOKEN" ]; then
  # crear si no existe
  curl -s -o /dev/null -X POST "$API/auth/register" -H "Content-Type: application/json" \
    -d '{"name":"E2E","email":"e2e@cliente.com","phone":"3000000000","password":"E2eTest1234*"}'
  CLIENT=$(login "e2e@cliente.com" "E2eTest1234*")
  TOKEN=$(echo "$CLIENT" | extract_field access_token)
fi
ok "Token cliente obtenido"

step "Vaciar carrito + agregar 1 producto (variante 6: GOR-AZU stock=18)"
curl -s -o /dev/null -X DELETE "$API/cart" -H "Authorization: Bearer $TOKEN"
ADD=$(curl -s -X POST "$API/cart/items" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"variant_id":6,"quantity":1}')
if echo "$ADD" | grep -q "subtotal"; then
  ok "Carrito preparado"
else
  fail "No se pudo preparar carrito: $ADD"
  summary; exit 1
fi

step ">>> EXPERIMENTO: docker compose stop inventory-service"
docker compose stop inventory-service >/dev/null 2>&1
ok "Inventory detenido"
sleep 2

step "HIPOTESIS 1: Catalog sigue respondiendo"
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/catalog")
assert_eq "$code" "200" "GET /api/catalog sigue 200 con Inventory caido"
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/products")
assert_eq "$code" "200" "GET /api/products sigue 200"

step "HIPOTESIS 2: detalle de producto degrada (variants vacio, inventory_available=false)"
DETAIL=$(curl -s "$API/products/3")
INV_OK=$(echo "$DETAIL" | python -c "import sys,json;print(json.load(sys.stdin)['inventory_available'])")
assert_eq "$INV_OK" "False" "inventory_available es false cuando Inventory esta caido"

step "HIPOTESIS 3: Inventory devuelve 502 desde gateway"
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/inventory/variants/6")
if [ "$code" = "502" ] || [ "$code" = "503" ] || [ "$code" = "504" ]; then
  ok "/api/inventory/variants/6 devuelve $code (esperado 502/503/504)"
else
  warn "/api/inventory/variants/6 devuelve $code (esperaba 5xx)"
fi

step "HIPOTESIS 4: Checkout falla controlado, NO crea orden PAID"
CHECKOUT=$(curl -s -X POST "$API/checkout" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: chaos-inv-$(date +%s)" \
  -d '{"delivery_name":"E2E","delivery_address":"Calle 100 #1","delivery_city":"Bogota","billing_document":"1024","contact_phone":"3001112233","contact_email":"e2e@cliente.com"}')
STATUS=$(echo "$CHECKOUT" | extract_field status)
if [ "$STATUS" = "SIN_STOCK" ] || [ "$STATUS" = "PAGO_PENDIENTE" ] || [ "$STATUS" = "CREATED" ]; then
  ok "Checkout devuelve estado controlado: $STATUS"
else
  fail "Checkout devolvio estado inesperado: $STATUS - body: $CHECKOUT"
fi
# Asegurar que NO quedo PAID
if [ "$STATUS" = "PAID" ]; then
  fail "ERROR CRITICO: orden quedo PAID sin haber pagado realmente"
else
  ok "No se creo orden PAID falsa"
fi

step "HIPOTESIS 5: Restaurar Inventory + verificar recuperacion"
docker compose start inventory-service >/dev/null 2>&1
info "Esperando que Inventory vuelva healthy..."
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost/health/inventory")
  if [ "$code" = "200" ]; then break; fi
  sleep 2
done
assert_eq "$code" "200" "Inventory volvio healthy"

step "HIPOTESIS 6: Nuevo checkout funciona normal tras la recuperacion"
sleep 2
CHECKOUT2=$(curl -s -X POST "$API/checkout" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: chaos-recover-$(date +%s)" \
  -d '{"delivery_name":"E2E","delivery_address":"Calle 100 #2","delivery_city":"Bogota","billing_document":"1024","contact_phone":"3001112233","contact_email":"e2e@cliente.com"}')
STATUS2=$(echo "$CHECKOUT2" | extract_field status)
assert_eq "$STATUS2" "PAID" "Checkout despues de recuperar Inventory devuelve PAID"

summary
