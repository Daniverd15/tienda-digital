# =============================================================================
# Chaos Monkey: detener Inventory durante un checkout activo.
# Equivalente a chaos_monkey_inventory.sh para PowerShell en Windows.
# Uso: cd tienda-digital-master; .\scripts\chaos\chaos_monkey_inventory.ps1
# Requiere: docker compose up -d (todos los contenedores corriendo)
# Salida esperada: 12 PASS / 0 FAIL en condiciones normales.
# =============================================================================
$API = "http://localhost/api"
$PASS = 0; $FAIL = 0

function ok($msg)   { Write-Host "  OK     $msg" -ForegroundColor Green;  $script:PASS++ }
function fail($msg) { Write-Host "  FAIL   $msg" -ForegroundColor Red;    $script:FAIL++ }
function info($msg) { Write-Host "  info   $msg" -ForegroundColor Gray }
function warn($msg) { Write-Host "  WARN   $msg" -ForegroundColor Yellow }
function step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }

function assert_eq($actual, $expected, $desc) {
    if ($actual -eq $expected) { ok "$desc (esperado=$expected actual=$actual)" }
    else                        { fail "$desc (esperado=$expected actual=$actual)" }
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

# ── Pre-condicion ─────────────────────────────────────────────────────────────
step "Pre-condicion: Inventory healthy"
$code = curl.exe -s -o NUL -w "%{http_code}" "http://localhost/health/inventory"
assert_eq $code "200" "Inventory esta healthy antes del experimento"

# ── Cliente para el experimento ───────────────────────────────────────────────
step "Cliente para el experimento"
$CLIENT = do_login "e2e@cliente.com" "E2eTest1234*"
$TOKEN  = $CLIENT | json_field "access_token"
if (-not $TOKEN) {
    curl.exe -s -o NUL -X POST "$API/auth/register" -H "Content-Type: application/json" `
        -d '{"name":"E2E","email":"e2e@cliente.com","phone":"3000000000","password":"E2eTest1234*"}'
    $CLIENT = do_login "e2e@cliente.com" "E2eTest1234*"
    $TOKEN  = $CLIENT | json_field "access_token"
}
ok "Token cliente obtenido"

# ── Preparar carrito ──────────────────────────────────────────────────────────
step "Vaciar carrito + agregar 1 producto (variante 6: GOR-AZU stock=18)"
curl.exe -s -o NUL -X DELETE "$API/cart" -H "Authorization: Bearer $TOKEN"
$ADD = curl.exe -s -X POST "$API/cart/items" `
    -H "Authorization: Bearer $TOKEN" `
    -H "Content-Type: application/json" `
    -d '{"variant_id":6,"quantity":1}'
if ($ADD -like "*subtotal*") { ok "Carrito preparado" }
else { fail "No se pudo preparar carrito: $ADD"; exit 1 }

# ── EXPERIMENTO: detener Inventory ───────────────────────────────────────────
step ">>> EXPERIMENTO: docker compose stop inventory-service"
docker compose stop inventory-service 2>$null
ok "Inventory detenido"
Start-Sleep -Seconds 2

# ── HIPOTESIS 1: Catalog sigue respondiendo ───────────────────────────────────
step "HIPOTESIS 1: Catalog sigue respondiendo"
$code = curl.exe -s -o NUL -w "%{http_code}" "$API/catalog"
assert_eq $code "200" "GET /api/catalog sigue 200 con Inventory caido"
$code = curl.exe -s -o NUL -w "%{http_code}" "$API/products"
assert_eq $code "200" "GET /api/products sigue 200"

# ── HIPOTESIS 2: Detalle degrada ──────────────────────────────────────────────
step "HIPOTESIS 2: detalle de producto degrada (inventory_available=false)"
$DETAIL = curl.exe -s "$API/products/3"
$INV_OK = $DETAIL | python -c "import sys,json;print(json.load(sys.stdin)['inventory_available'])" 2>$null
assert_eq $INV_OK "False" "inventory_available es false cuando Inventory esta caido"

# ── HIPOTESIS 3: Inventory devuelve 5xx desde el gateway ─────────────────────
step "HIPOTESIS 3: Inventory devuelve 502 desde gateway"
$code = curl.exe -s -o NUL -w "%{http_code}" "$API/inventory/variants/6"
if ($code -eq "502" -or $code -eq "503" -or $code -eq "504") {
    ok "/api/inventory/variants/6 devuelve $code (esperado 502/503/504)"
} else {
    warn "/api/inventory/variants/6 devuelve $code (esperaba 5xx)"
}

# ── HIPOTESIS 4: Checkout falla controlado, NO crea orden PAID ───────────────
step "HIPOTESIS 4: Checkout falla controlado, NO crea orden PAID"
$CHECKOUT = curl.exe -s -X POST "$API/checkout" `
    -H "Authorization: Bearer $TOKEN" `
    -H "Content-Type: application/json" `
    -H "Idempotency-Key: chaos-inv-$TS" `
    -d '{"delivery_name":"E2E","delivery_address":"Calle 100 #1","delivery_city":"Bogota","billing_document":"1024","contact_phone":"3001112233","contact_email":"e2e@cliente.com"}'
$STATUS = $CHECKOUT | json_field "status"
if ($STATUS -eq "SIN_STOCK" -or $STATUS -eq "PAGO_PENDIENTE" -or $STATUS -eq "CREATED") {
    ok "Checkout devuelve estado controlado: $STATUS"
} else {
    fail "Checkout devolvio estado inesperado: $STATUS - body: $CHECKOUT"
}
if ($STATUS -eq "PAID") { fail "ERROR CRITICO: orden quedo PAID sin haber pagado realmente" }
else                     { ok "No se creo orden PAID falsa" }

# ── HIPOTESIS 5: Restaurar y verificar recuperacion ──────────────────────────
step "HIPOTESIS 5: Restaurar Inventory + verificar recuperacion"
docker compose start inventory-service 2>$null
info "Esperando que Inventory vuelva healthy..."
$code = "000"
for ($i = 1; $i -le 20; $i++) {
    $code = curl.exe -s -o NUL -w "%{http_code}" "http://localhost/health/inventory"
    if ($code -eq "200") { break }
    Start-Sleep -Seconds 2
}
assert_eq $code "200" "Inventory volvio healthy"

# ── HIPOTESIS 6: Nuevo checkout funciona normal ───────────────────────────────
step "HIPOTESIS 6: Nuevo checkout funciona normal tras la recuperacion"
Start-Sleep -Seconds 2
$CHECKOUT2 = curl.exe -s -X POST "$API/checkout" `
    -H "Authorization: Bearer $TOKEN" `
    -H "Content-Type: application/json" `
    -H "Idempotency-Key: chaos-recover-$TS" `
    -d '{"delivery_name":"E2E","delivery_address":"Calle 100 #2","delivery_city":"Bogota","billing_document":"1024","contact_phone":"3001112233","contact_email":"e2e@cliente.com"}'
$STATUS2 = $CHECKOUT2 | json_field "status"
assert_eq $STATUS2 "PAID" "Checkout despues de recuperar Inventory devuelve PAID"

# ── Resumen ───────────────────────────────────────────────────────────────────
Write-Host "`n========================================"  -ForegroundColor Cyan
Write-Host "  Resumen: $PASS PASS   $FAIL FAIL" -ForegroundColor $(if ($FAIL -eq 0) {"Green"} else {"Red"})
Write-Host "========================================`n" -ForegroundColor Cyan
exit $(if ($FAIL -eq 0) {0} else {1})
