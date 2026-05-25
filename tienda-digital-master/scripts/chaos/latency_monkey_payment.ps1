# =============================================================================
# Latency Monkey: forzar fallos repetidos en la pasarela y verificar que el
# Circuit Breaker abre + el checkout degrada de forma graceful.
# Equivalente a latency_monkey_payment.sh para PowerShell en Windows.
# Uso: cd tienda-digital-master; .\scripts\chaos\latency_monkey_payment.ps1
# Requiere: docker compose up -d (todos los contenedores corriendo)
# Salida esperada: 9 PASS / 0 FAIL en condiciones normales.
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

# ── Login admin ───────────────────────────────────────────────────────────────
step "Login admin (necesario para inspeccionar y resetear el CB)"
$ADMIN  = do_login "admin@tienda.com" "Admin1234*"
$ATOKEN = $ADMIN | json_field "access_token"
if ($ATOKEN) { ok "Admin token" }
else          { fail "Admin login fallo"; exit 1 }

# ── Reset previo del CB ───────────────────────────────────────────────────────
step "Reset previo del CB"
curl.exe -s -o NUL -X POST "$API/payments/circuit/reset" -H "Authorization: Bearer $ATOKEN"
$INIT = curl.exe -s "$API/payments/circuit/state" -H "Authorization: Bearer $ATOKEN"
$ST   = $INIT | json_field "state"
assert_eq $ST "CLOSED" "CB inicial CLOSED"

# ── Provocar 5 fallos ─────────────────────────────────────────────────────────
step "Provocar 5 fallos consecutivos con monto .88 (mock devuelve 500)"
for ($i = 1; $i -le 5; $i++) {
    $body = "{`"order_id`":`"LAT-MK-$i-$TS`",`"amount`":50000.88}"
    curl.exe -s -o NUL -X POST "$API/payments" `
        -H "Authorization: Bearer $ATOKEN" `
        -H "Content-Type: application/json" `
        -d $body
    info "intento $i disparado"
}

# ── HIPOTESIS 1: CB en OPEN ───────────────────────────────────────────────────
step "HIPOTESIS 1: CB esta OPEN"
$ST_AFTER = curl.exe -s "$API/payments/circuit/state" -H "Authorization: Bearer $ATOKEN"
$STATE    = $ST_AFTER | json_field "state"
assert_eq $STATE "OPEN" "CB abierto tras 5 fallos"
$FAILURES = $ST_AFTER | python -c "import sys,json;print(json.load(sys.stdin)['failures'])" 2>$null
if ([int]$FAILURES -ge 5) { ok "Contador de fallos = $FAILURES (>=5)" }
else                       { fail "Contador insuficiente: $FAILURES" }

# ── HIPOTESIS 2: Rechazo rapido sin tocar el mock ────────────────────────────
step "HIPOTESIS 2: Nuevo charge se rechaza inmediato con 503 SIN tocar la pasarela"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$code = curl.exe -s -o NUL -w "%{http_code}" -X POST "$API/payments" `
    -H "Authorization: Bearer $ATOKEN" `
    -H "Content-Type: application/json" `
    -d "{`"order_id`":`"LAT-CB-FAST-$TS`",`"amount`":50000.00}"
$sw.Stop()
$ms = $sw.ElapsedMilliseconds
assert_eq $code "503" "POST /payments con CB abierto devuelve 503"
if ($ms -lt 500) { ok "Respuesta inmediata (${ms}ms < 500ms, sin tocar mock)" }
else              { warn "Respuesta tomo ${ms}ms (CB deberia ser <100ms; revisar)" }

# ── HIPOTESIS 3: Checkout con CB abierto devuelve 503 ────────────────────────
step "HIPOTESIS 3: Checkout completo con CB abierto devuelve 503 (sin crear Order falsa)"
$CLIENT = do_login "e2e@cliente.com" "E2eTest1234*"
$CTOKEN = $CLIENT | json_field "access_token"
if (-not $CTOKEN) {
    curl.exe -s -o NUL -X POST "$API/auth/register" -H "Content-Type: application/json" `
        -d '{"name":"E2E","email":"e2e@cliente.com","phone":"3000000000","password":"E2eTest1234*"}'
    $CLIENT = do_login "e2e@cliente.com" "E2eTest1234*"
    $CTOKEN = $CLIENT | json_field "access_token"
}
curl.exe -s -o NUL -X DELETE "$API/cart" -H "Authorization: Bearer $CTOKEN"
curl.exe -s -o NUL -X POST "$API/cart/items" `
    -H "Authorization: Bearer $CTOKEN" `
    -H "Content-Type: application/json" `
    -d '{"variant_id":11,"quantity":1}'
$CK_TMPFILE = "$env:TEMP\_ck_lat_$TS.json"
$HTTP_CODE = curl.exe -s -o $CK_TMPFILE -w "%{http_code}" -X POST "$API/checkout" `
    -H "Authorization: Bearer $CTOKEN" `
    -H "Content-Type: application/json" `
    -H "Idempotency-Key: lat-$TS" `
    -d '{"delivery_name":"E2E","delivery_address":"Calle 100 #20","delivery_city":"Bogota","billing_document":"1024","contact_phone":"3001112233","contact_email":"e2e@cliente.com"}'
$CK_BODY = Get-Content $CK_TMPFILE -Raw -ErrorAction SilentlyContinue
$CK_CODE = $CK_BODY | json_field "code"
if ($HTTP_CODE -eq "503" -and $CK_CODE -eq "payment_unavailable") {
    ok "Checkout responde 503 payment_unavailable con CB abierto (degradacion graceful, sin Order)"
} else {
    fail "Checkout deberia devolver 503/payment_unavailable; obtuvo http=$HTTP_CODE code=$CK_CODE"
}

# ── HIPOTESIS 4: Reset admin del CB ──────────────────────────────────────────
step "HIPOTESIS 4: Reset admin del CB"
curl.exe -s -o NUL -X POST "$API/payments/circuit/reset" -H "Authorization: Bearer $ATOKEN"
$RESET = curl.exe -s "$API/payments/circuit/state" -H "Authorization: Bearer $ATOKEN"
$RST   = $RESET | json_field "state"
assert_eq $RST "CLOSED" "CB vuelve a CLOSED tras reset"

# ── HIPOTESIS 5: Charge normal tras recovery ──────────────────────────────────
step "HIPOTESIS 5: Nuevo charge tras reset funciona normal"
$R = curl.exe -s -X POST "$API/payments" `
    -H "Authorization: Bearer $ATOKEN" `
    -H "Content-Type: application/json" `
    -d "{`"order_id`":`"LAT-RECOVER-$TS`",`"amount`":50000.00}"
$RST_STATUS = $R | json_field "status"
assert_eq $RST_STATUS "APPROVED" "Charge .00 tras reset = APPROVED"

# ── Resumen ───────────────────────────────────────────────────────────────────
Write-Host "`n========================================"  -ForegroundColor Cyan
Write-Host "  Resumen: $PASS PASS   $FAIL FAIL" -ForegroundColor $(if ($FAIL -eq 0) {"Green"} else {"Red"})
Write-Host "========================================`n" -ForegroundColor Cyan
exit $(if ($FAIL -eq 0) {0} else {1})
