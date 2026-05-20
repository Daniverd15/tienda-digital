#!/usr/bin/env bash
# Suite E2E del flujo principal de Tienda Digital.
# Recorre los 5 microservicios y valida el contrato esperado.
#
# Uso:
#   docker compose up -d
#   ./scripts/e2e/flujo_completo.sh

set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$DIR/_helpers.sh"

USER_EMAIL="${E2E_USER_EMAIL:-e2e-test-$(date +%s)@cliente.com}"
USER_PASS="E2eTest1234*"

step "Pre-condicion: 6 healthchecks"
for svc in gateway auth catalog inventory commerce payment; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost/health/$svc")
  assert_eq "$code" "200" "health/$svc responde 200"
done

step "1. Registrar cliente nuevo"
REG=$(curl -s -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"E2E Test\",\"email\":\"$USER_EMAIL\",\"phone\":\"3001112233\",\"password\":\"$USER_PASS\"}")
CLIENT_TOKEN=$(echo "$REG" | extract_field access_token)
USER_ID=$(echo "$REG" | python -c "import sys,json;d=json.load(sys.stdin);print(d['user']['id'])" 2>/dev/null)
if [ -n "$CLIENT_TOKEN" ]; then
  ok "Registro de cliente (user_id=$USER_ID)"
else
  fail "Registro de cliente fallo: $REG"
  summary; exit 1
fi

step "2. Login con las credenciales recien creadas"
LOGIN=$(login "$USER_EMAIL" "$USER_PASS")
NEW_TOKEN=$(echo "$LOGIN" | extract_field access_token)
[ -n "$NEW_TOKEN" ] && ok "Login OK" || fail "Login fallo"
CLIENT_TOKEN="$NEW_TOKEN"

step "3. Login admin"
ADMIN_LOGIN=$(login "admin@tienda.com" "Admin1234*")
ADMIN_TOKEN=$(echo "$ADMIN_LOGIN" | extract_field access_token)
[ -n "$ADMIN_TOKEN" ] && ok "Admin login OK" || fail "Admin login fallo"

step "4. /auth/me devuelve el perfil correcto"
ME=$(curl -s "$API/auth/me" -H "Authorization: Bearer $CLIENT_TOKEN")
assert_contains "$ME" "$USER_EMAIL" "/auth/me trae el email del cliente"
assert_contains "$ME" "\"role\":\"customer\"" "/auth/me trae role=customer"

step "5. Catalogo publico"
CAT=$(curl -s "$API/catalog")
assert_contains "$CAT" "Distrito Urbano" "Catalog overview trae commercial_name"
PRODS=$(curl -s "$API/products")
assert_contains "$PRODS" "Camiseta basica negra" "Lista de productos trae el seed"

step "6. Detalle de producto trae variantes enriquecidas desde Inventory"
DETAIL=$(curl -s "$API/products/1")
assert_contains "$DETAIL" "\"inventory_available\":true" "Detalle expone flag inventory_available"
assert_contains "$DETAIL" "\"sku\":\"CAM-NEG-S\"" "Detalle expone SKU de Inventory"

step "7. Carrito vacio al inicio"
CART=$(curl -s "$API/cart" -H "Authorization: Bearer $CLIENT_TOKEN")
ITEM_COUNT=$(echo "$CART" | python -c "import sys,json;print(json.load(sys.stdin)['item_count'])" 2>/dev/null)
assert_eq "$ITEM_COUNT" "0" "Carrito recien creado tiene 0 items"
# Snapshot del stock previo al checkout (para verificar la baja real)
PRE_AVAIL=$(curl -s "$API/inventory/variants/1" | python -c "import sys,json;print(json.load(sys.stdin)['available'])")

step "8. Agregar 2 productos al carrito"
curl -s -o /dev/null -X POST "$API/cart/items" \
  -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
  -d '{"variant_id":1,"quantity":2}'
curl -s -o /dev/null -X POST "$API/cart/items" \
  -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" \
  -d '{"variant_id":6,"quantity":1}'
CART=$(curl -s "$API/cart" -H "Authorization: Bearer $CLIENT_TOKEN")
ITEM_COUNT=$(echo "$CART" | python -c "import sys,json;print(json.load(sys.stdin)['item_count'])")
assert_eq "$ITEM_COUNT" "3" "Carrito ahora tiene 3 unidades"
SUBTOTAL=$(echo "$CART" | python -c "import sys,json;print(json.load(sys.stdin)['subtotal'])")
assert_eq "$SUBTOTAL" "133000.0" "Subtotal calculado correctamente (2x49000 + 35000)"

step "9. Checkout con monto APPROVED (.00)"
CHECKOUT=$(curl -s -X POST "$API/checkout" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: e2e-$(date +%s)" \
  -d '{
    "delivery_name":"E2E Test",
    "delivery_address":"Calle 100 #20-30",
    "delivery_city":"Bogota",
    "billing_document":"1024567890",
    "contact_phone":"3001112233",
    "contact_email":"'$USER_EMAIL'"
  }')
ORDER_STATUS=$(echo "$CHECKOUT" | extract_field status)
PAY_STATUS=$(echo "$CHECKOUT" | extract_field payment_status)
ORDER_ID=$(echo "$CHECKOUT" | extract_field order_id)
ORDER_CODE=$(echo "$CHECKOUT" | extract_field order_code)
assert_eq "$ORDER_STATUS" "PAID" "Orden quedo en estado PAID tras APPROVED"
assert_eq "$PAY_STATUS" "APPROVED" "Pago aprobado"
info "Order ID: $ORDER_ID  /  Code: $ORDER_CODE"

step "10. Stock real bajo en Inventory tras checkout"
# Snapshot pre-checkout esta en $PRE_AVAIL (capturado en paso 7). Verificamos
# que el stock haya bajado en >= la cantidad comprada (2 unidades).
VAR1=$(curl -s "$API/inventory/variants/1")
AVAIL=$(echo "$VAR1" | python -c "import sys,json;print(json.load(sys.stdin)['available'])")
DROP=$(( PRE_AVAIL - AVAIL ))
if [ "$DROP" -ge 2 ]; then
  ok "Variante 1 available=$AVAIL (bajo ${DROP} unidades desde ${PRE_AVAIL})"
else
  fail "Stock no bajo lo suficiente: pre=$PRE_AVAIL post=$AVAIL drop=$DROP"
fi

step "11. /orders/mine trae la orden recien creada"
MINE=$(curl -s "$API/orders/mine" -H "Authorization: Bearer $CLIENT_TOKEN")
assert_contains "$MINE" "\"order_code\":\"$ORDER_CODE\"" "Pedido aparece en historial"

step "12. /orders/{id} trae historia con paso a PAID"
# Politica del MVP: la Order solo se persiste si el checkout llega a PAID,
# asi que el historial arranca directo en PAID (sin estados intermedios).
DETAIL_ORDER=$(curl -s "$API/orders/$ORDER_ID" -H "Authorization: Bearer $CLIENT_TOKEN")
assert_contains "$DETAIL_ORDER" "\"to_status\":\"PAID\"" "History incluye paso a PAID"

step "13. Notificaciones del cliente"
NOTIFS=$(curl -s "$API/notifications" -H "Authorization: Bearer $CLIENT_TOKEN")
COUNT=$(echo "$NOTIFS" | python -c "import sys,json;print(len(json.load(sys.stdin)))")
if [ "$COUNT" -ge 1 ]; then
  ok "Cliente tiene $COUNT notificaciones"
else
  fail "Cliente no recibio notificaciones"
fi

step "14. Admin transiciona: PAID -> EN_PREPARACION -> ENVIADO -> ENTREGADO"
for new in EN_PREPARACION ENVIADO ENTREGADO; do
  R=$(curl -s -X PATCH "$API/admin/orders/$ORDER_ID/status" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"new_status\":\"$new\",\"notes\":\"e2e\"}")
  GOT=$(echo "$R" | extract_field status)
  assert_eq "$GOT" "$new" "Transicion a $new"
done

step "15. Cliente crea resena del producto 1 (comprado y entregado)"
REVIEW=$(curl -s -X POST "$API/reviews" \
  -H "Authorization: Bearer $CLIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"product_id\":1,\"order_id\":$ORDER_ID,\"rating\":5,\"comment\":\"E2E test review\"}")
REVIEW_ID=$(echo "$REVIEW" | extract_field id)
[ -n "$REVIEW_ID" ] && ok "Resena creada id=$REVIEW_ID (pendiente de aprobacion)" || fail "Resena fallo: $REVIEW"

step "16. Admin aprueba la resena y Catalog refleja el rating en su Cache-Aside"
curl -s -o /dev/null -X PATCH "$API/admin/reviews/$REVIEW_ID/approve" -H "Authorization: Bearer $ADMIN_TOKEN"
sleep 1
P1=$(curl -s "$API/products/1")
RAT=$(echo "$P1" | python -c "import sys,json;d=json.load(sys.stdin);print(d['average_rating'])")
if [ "$(python -c "print(float('$RAT') >= 1.0)")" = "True" ]; then
  ok "Catalog tiene rating=$RAT tras aprobacion admin (>= 1)"
else
  fail "Catalog rating=$RAT no se actualizo tras aprobacion"
fi

step "17. Casos negativos"
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/me")
assert_eq "$code" "401" "GET /auth/me sin token devuelve 401"
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/admin/customers" -H "Authorization: Bearer $CLIENT_TOKEN")
assert_eq "$code" "403" "GET /admin/customers con token customer devuelve 403"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/auth/login" \
  -H "Content-Type: application/json" -d '{"email":"admin@tienda.com","password":"INCORRECTA"}')
assert_eq "$code" "401" "Login con clave mala devuelve 401"

step "18. Resumen financiero admin"
FIN=$(curl -s "$API/admin/finance/summary" -H "Authorization: Bearer $ADMIN_TOKEN")
GROSS=$(echo "$FIN" | python -c "import sys,json;print(json.load(sys.stdin)['gross_sales'])")
if [ "$(python -c "print(float('$GROSS') >= 133000)")" = "True" ]; then
  ok "Finance summary refleja ventas (gross_sales=$GROSS)"
else
  fail "Finance summary gross_sales=$GROSS"
fi

summary
