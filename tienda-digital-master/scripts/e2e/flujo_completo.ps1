# =============================================================================
# Suite E2E - Flujo Completo (PowerShell)
# Equivalente a flujo_completo.sh para ejecutar desde PowerShell en Windows.
# Uso: cd tienda-digital-master; .\scripts\e2e\flujo_completo.ps1
# Requiere: docker compose up -d (todos los contenedores corriendo)
# =============================================================================
$API = "http://localhost/api"
$PASS = 0; $FAIL = 0

function ok($msg)   { Write-Host "  OK     $msg" -ForegroundColor Green;  $script:PASS++ }
function fail($msg) { Write-Host "  FAIL   $msg" -ForegroundColor Red;    $script:FAIL++ }
function info($msg) { Write-Host "  info   $msg" -ForegroundColor Gray }
function step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }

function assert_eq($actual, $expected, $desc) {
    if ($actual -eq $expected) { ok "$desc (esperado=$expected actual=$actual)" }
    else                        { fail "$desc (esperado=$expected actual=$actual)" }
}
function assert_contains($haystack, $needle, $desc) {
    if ($haystack -like "*$needle*") { ok $desc }
    else                              { fail "$desc -- '$needle' no encontrado" }
}
function json_field($json, $field) {
    try { ($json | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('$field',''))") }
    catch { "" }
}
function do_login($email, $pass) {
    $body = "{`"email`":`"$email`",`"password`":`"$pass`"}"
    curl.exe -s -X POST "$API/auth/login" -H "Content-Type: application/json" -d $body
}

$TS = [int](Get-Date -UFormat %s)
$USER_EMAIL = "e2e-ps-$TS@cliente.com"
$USER_PASS  = "E2eTest1234*"

# ── Pre-condicion ────────────────────────────────────────────────────────────
step "Pre-condicion: 6 healthchecks"
foreach ($svc in @("gateway","auth","catalog","inventory","commerce","payment")) {
    $code = curl.exe -s -o NUL -w "%{http_code}" "http://localhost/health/$svc"
    assert_eq $code "200" "health/$svc responde 200"
}

# ── Paso 1: Registro ─────────────────────────────────────────────────────────
step "1. Registrar cliente nuevo"
$body = "{`"name`":`"E2E PS`",`"email`":`"$USER_EMAIL`",`"phone`":`"3001112233`",`"password`":`"$USER_PASS`"}"
$REG = curl.exe -s -X POST "$API/auth/register" -H "Content-Type: application/json" -d $body
$CLIENT_TOKEN = $REG | json_field "access_token"
$USER_ID = $REG | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('user',{}).get('id',''))" 2>$null
if ($CLIENT_TOKEN) { ok "Registro de cliente (user_id=$USER_ID)" }
else               { fail "Registro fallo: $REG"; Write-Host "ABORT"; exit 1 }

# ── Paso 2: Login ────────────────────────────────────────────────────────────
step "2. Login con credenciales recien creadas"
$LOGIN = do_login $USER_EMAIL $USER_PASS
$NEW_TOKEN = $LOGIN | json_field "access_token"
if ($NEW_TOKEN) { ok "Login OK"; $CLIENT_TOKEN = $NEW_TOKEN }
else            { fail "Login fallo" }

# ── Paso 3: Login admin ──────────────────────────────────────────────────────
step "3. Login admin"
$ADMIN_LOGIN = do_login "admin@tienda.com" "Admin1234*"
$ADMIN_TOKEN = $ADMIN_LOGIN | json_field "access_token"
if ($ADMIN_TOKEN) { ok "Admin login OK" } else { fail "Admin login fallo" }

# ── Paso 4: /auth/me ─────────────────────────────────────────────────────────
step "4. /auth/me devuelve el perfil correcto"
$ME = curl.exe -s "$API/auth/me" -H "Authorization: Bearer $CLIENT_TOKEN"
assert_contains $ME $USER_EMAIL "/auth/me trae el email del cliente"
assert_contains $ME '"role":"customer"' "/auth/me trae role=customer"

# ── Paso 5: Catalogo ─────────────────────────────────────────────────────────
step "5. Catalogo publico"
$CAT = curl.exe -s "$API/catalog"
assert_contains $CAT "Distrito Urbano" "Catalog overview trae commercial_name"
$PRODS = curl.exe -s "$API/products"
assert_contains $PRODS "Camiseta" "Lista de productos trae el seed"

# ── Paso 6: Detalle producto ──────────────────────────────────────────────────
step "6. Detalle de producto trae variantes de Inventory"
$DETAIL = curl.exe -s "$API/products/1"
assert_contains $DETAIL '"inventory_available":true' "Detalle expone inventory_available"
assert_contains $DETAIL '"sku":"CAM-NEG-S"' "Detalle expone SKU de Inventory"

# ── Paso 7: Carrito vacio ─────────────────────────────────────────────────────
step "7. Carrito vacio al inicio"
$CART = curl.exe -s "$API/cart" -H "Authorization: Bearer $CLIENT_TOKEN"
$ITEM_COUNT = $CART | python -c "import sys,json;print(json.load(sys.stdin)['item_count'])" 2>$null
assert_eq $ITEM_COUNT "0" "Carrito recien creado tiene 0 items"
$PRE_AVAIL = curl.exe -s "$API/inventory/variants/1" | python -c "import sys,json;print(json.load(sys.stdin)['available'])" 2>$null

# ── Paso 8: Agregar productos ─────────────────────────────────────────────────
step "8. Agregar 2 productos al carrito"
curl.exe -s -o NUL -X POST "$API/cart/items" -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" -d '{"variant_id":1,"quantity":2}'
curl.exe -s -o NUL -X POST "$API/cart/items" -H "Authorization: Bearer $CLIENT_TOKEN" -H "Content-Type: application/json" -d '{"variant_id":6,"quantity":1}'
$CART2 = curl.exe -s "$API/cart" -H "Authorization: Bearer $CLIENT_TOKEN"
$ITEM_COUNT2 = $CART2 | python -c "import sys,json;print(json.load(sys.stdin)['item_count'])" 2>$null
$SUBTOTAL = $CART2 | python -c "import sys,json;print(json.load(sys.stdin)['subtotal'])" 2>$null
assert_eq $ITEM_COUNT2 "3" "Carrito tiene 3 unidades"
assert_eq $SUBTOTAL "133000.0" "Subtotal calculado correctamente (2x49000 + 35000)"

# ── Paso 9: Checkout APPROVED ──────────────────────────────────────────────────
step "9. Checkout con monto APPROVED (.00)"
$CK_BODY = "{`"delivery_name`":`"E2E PS`",`"delivery_address`":`"Calle 100 #20`",`"delivery_city`":`"Bogota`",`"billing_document`":`"1024567890`",`"contact_phone`":`"3001112233`",`"contact_email`":`"$USER_EMAIL`"}"
$CHECKOUT = curl.exe -s -X POST "$API/checkout" `
    -H "Authorization: Bearer $CLIENT_TOKEN" `
    -H "Content-Type: application/json" `
    -H "Idempotency-Key: e2e-ps-$TS" `
    -d $CK_BODY
$ORDER_STATUS = $CHECKOUT | json_field "status"
$PAY_STATUS   = $CHECKOUT | json_field "payment_status"
$ORDER_ID     = $CHECKOUT | json_field "order_id"
$ORDER_CODE   = $CHECKOUT | json_field "order_code"
assert_eq $ORDER_STATUS "PAID"     "Orden quedo en PAID tras APPROVED"
assert_eq $PAY_STATUS "APPROVED"   "Pago aprobado"
info "Order ID: $ORDER_ID  /  Code: $ORDER_CODE"

# ── Paso 10: Stock bajo ────────────────────────────────────────────────────────
step "10. Stock real bajo en Inventory tras checkout"
$AVAIL = curl.exe -s "$API/inventory/variants/1" | python -c "import sys,json;print(json.load(sys.stdin)['available'])" 2>$null
$DROP = [int]$PRE_AVAIL - [int]$AVAIL
if ($DROP -ge 2) { ok "Variante 1 available=$AVAIL (bajo $DROP unidades desde $PRE_AVAIL)" }
else             { fail "Stock no bajo suficiente: pre=$PRE_AVAIL post=$AVAIL" }

# ── Paso 11: /orders/mine ─────────────────────────────────────────────────────
step "11. /orders/mine trae la orden recien creada"
$MINE = curl.exe -s "$API/orders/mine" -H "Authorization: Bearer $CLIENT_TOKEN"
assert_contains $MINE $ORDER_CODE "Pedido aparece en historial"

# ── Paso 12: History ──────────────────────────────────────────────────────────
step "12. /orders/{id} trae historia con paso a PAID"
$DORD = curl.exe -s "$API/orders/$ORDER_ID" -H "Authorization: Bearer $CLIENT_TOKEN"
assert_contains $DORD '"to_status":"PAID"' "History incluye paso a PAID"

# ── Paso 13: Notificaciones ───────────────────────────────────────────────────
step "13. Notificaciones del cliente"
$NOTIFS = curl.exe -s "$API/notifications" -H "Authorization: Bearer $CLIENT_TOKEN"
$COUNT = $NOTIFS | python -c "import sys,json;print(len(json.load(sys.stdin)))" 2>$null
if ([int]$COUNT -ge 1) { ok "Cliente tiene $COUNT notificaciones" }
else                    { fail "Cliente no recibio notificaciones" }

# ── Paso 14: Transiciones admin ───────────────────────────────────────────────
step "14. Admin transiciona: PAID -> EN_PREPARACION -> ENVIADO -> ENTREGADO"
foreach ($new_status in @("EN_PREPARACION","ENVIADO","ENTREGADO")) {
    $R = curl.exe -s -X PATCH "$API/admin/orders/$ORDER_ID/status" `
        -H "Authorization: Bearer $ADMIN_TOKEN" `
        -H "Content-Type: application/json" `
        -d "{`"new_status`":`"$new_status`",`"notes`":`"e2e-ps`"}"
    $GOT = $R | json_field "status"
    assert_eq $GOT $new_status "Transicion a $new_status"
}

# ── Paso 15: Resena ───────────────────────────────────────────────────────────
step "15. Cliente crea resena del producto 1"
$REV = curl.exe -s -X POST "$API/reviews" `
    -H "Authorization: Bearer $CLIENT_TOKEN" `
    -H "Content-Type: application/json" `
    -d "{`"product_id`":1,`"order_id`":$ORDER_ID,`"rating`":5,`"comment`":`"E2E PowerShell test`"}"
$REVIEW_ID = $REV | json_field "id"
if ($REVIEW_ID) { ok "Resena creada id=$REVIEW_ID (pendiente de aprobacion)" }
else            { fail "Resena fallo: $REV" }

# ── Paso 16: Admin aprueba resena ──────────────────────────────────────────────
step "16. Admin aprueba resena + Catalog refleja rating (Cache-Aside)"
curl.exe -s -o NUL -X PATCH "$API/admin/reviews/$REVIEW_ID/approve" -H "Authorization: Bearer $ADMIN_TOKEN"
Start-Sleep -Seconds 1
$RAT = curl.exe -s "$API/products/1" | python -c "import sys,json;d=json.load(sys.stdin);print(d.get('average_rating',0))" 2>$null
$rat_ok = python -c "print(float('$RAT') >= 1.0)" 2>$null
if ($rat_ok -eq "True") { ok "Catalog tiene rating=$RAT tras aprobacion (>= 1)" }
else                     { fail "Catalog rating=$RAT no actualizado" }

# ── Paso 17: Casos negativos ──────────────────────────────────────────────────
step "17. Casos negativos"
$c1 = curl.exe -s -o NUL -w "%{http_code}" "$API/auth/me"
assert_eq $c1 "401" "GET /auth/me sin token devuelve 401"
$c2 = curl.exe -s -o NUL -w "%{http_code}" "$API/admin/customers" -H "Authorization: Bearer $CLIENT_TOKEN"
assert_eq $c2 "403" "GET /admin/customers con customer devuelve 403"
$c3 = curl.exe -s -o NUL -w "%{http_code}" -X POST "$API/auth/login" -H "Content-Type: application/json" -d '{"email":"admin@tienda.com","password":"INCORRECTA"}'
assert_eq $c3 "401" "Login con clave mala devuelve 401"

# ── Paso 18: Finance summary ──────────────────────────────────────────────────
step "18. Resumen financiero admin"
$FIN = curl.exe -s "$API/admin/finance/summary" -H "Authorization: Bearer $ADMIN_TOKEN"
$GROSS = $FIN | python -c "import sys,json;print(json.load(sys.stdin).get('gross_sales',0))" 2>$null
$fin_ok = python -c "print(float('$GROSS') >= 133000)" 2>$null
if ($fin_ok -eq "True") { ok "Finance summary refleja ventas (gross_sales=$GROSS)" }
else                     { fail "Finance summary gross_sales=$GROSS" }

# ── Resumen ───────────────────────────────────────────────────────────────────
Write-Host "`n========================================"  -ForegroundColor Cyan
Write-Host "  Resumen: $PASS PASS   $FAIL FAIL" -ForegroundColor $(if ($FAIL -eq 0) {"Green"} else {"Red"})
Write-Host "========================================`n" -ForegroundColor Cyan
exit $(if ($FAIL -eq 0) {0} else {1})
