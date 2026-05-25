# =============================================================================
# Security Monkey: el sistema valida autorizacion y rechaza accesos invalidos.
# Equivalente a security_monkey.sh para PowerShell en Windows.
# Uso: cd tienda-digital-master; .\scripts\chaos\security_monkey.ps1
# Requiere: docker compose up -d (todos los contenedores corriendo)
# Salida esperada: 27 PASS / 0 FAIL en condiciones normales.
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

# ── Cabeceras de seguridad ────────────────────────────────────────────────────
step "Cabeceras de seguridad en el gateway"
$HDR = curl.exe -sI "$API/catalog"
assert_contains $HDR "X-Content-Type-Options: nosniff" "Header X-Content-Type-Options presente"
assert_contains $HDR "X-Frame-Options: DENY"           "Header X-Frame-Options presente"
assert_contains $HDR "Referrer-Policy"                 "Header Referrer-Policy presente"

# ── Accesos sin JWT ───────────────────────────────────────────────────────────
step "Accesos sin JWT a recursos protegidos"
foreach ($path in @("/auth/me","/cart","/orders/mine","/notifications","/admin/customers","/admin/orders","/admin/inventory/variants")) {
    $code = curl.exe -s -o NUL -w "%{http_code}" "$API$path"
    assert_eq $code "401" "GET $path sin token -> 401"
}

# ── JWT corrupto ──────────────────────────────────────────────────────────────
step "Accesos con JWT corrupto"
$code = curl.exe -s -o NUL -w "%{http_code}" "$API/auth/me" -H "Authorization: Bearer not.a.jwt"
assert_eq $code "401" "JWT corrupto -> 401"
$code = curl.exe -s -o NUL -w "%{http_code}" "$API/auth/me" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature"
assert_eq $code "401" "JWT con firma invalida -> 401"

# ── Login admin + customer ────────────────────────────────────────────────────
step "Login admin + customer para pruebas de rol"
$ADMIN  = do_login "admin@tienda.com" "Admin1234*"
$ATOKEN = $ADMIN | json_field "access_token"
$CLIENT = do_login "e2e@cliente.com" "E2eTest1234*"
$CTOKEN = $CLIENT | json_field "access_token"
if (-not $CTOKEN) {
    curl.exe -s -o NUL -X POST "$API/auth/register" -H "Content-Type: application/json" `
        -d '{"name":"E2E","email":"e2e@cliente.com","phone":"3000000000","password":"E2eTest1234*"}'
    $CLIENT = do_login "e2e@cliente.com" "E2eTest1234*"
    $CTOKEN = $CLIENT | json_field "access_token"
}

# ── Customer no puede acceder a /admin ───────────────────────────────────────
step "Acceso a /admin con token de customer (deberia ser 403)"
foreach ($path in @("/admin/customers","/admin/orders","/admin/inventory/variants","/admin/finance/summary","/admin/employees","/admin/expenses")) {
    $code = curl.exe -s -o NUL -w "%{http_code}" "$API$path" -H "Authorization: Bearer $CTOKEN"
    assert_eq $code "403" "GET $path con token customer -> 403"
}

# ── Admin puede acceder a /admin ──────────────────────────────────────────────
step "Acceso a /admin con token de admin (deberia ser 200)"
foreach ($path in @("/admin/customers","/admin/orders","/admin/employees","/admin/expenses","/admin/audit-logs","/admin/finance/summary")) {
    $code = curl.exe -s -o NUL -w "%{http_code}" "$API$path" -H "Authorization: Bearer $ATOKEN"
    if ($code -eq "200") { ok "GET $path con admin -> 200" }
    else                  { fail "GET $path con admin -> $code (esperaba 200)" }
}

# ── IDOR: customer no puede ver pedidos ajenos ───────────────────────────────
step "Aislamiento: customer no puede ver pedidos de OTRO customer"
$MY_USER_ID = curl.exe -s "$API/auth/me" -H "Authorization: Bearer $CTOKEN" | json_field "id"
$OTHER_ORDER_ID = curl.exe -s "$API/admin/orders" -H "Authorization: Bearer $ATOKEN" | `
    python -c "import sys,json;rs=json.load(sys.stdin);me=$MY_USER_ID;ids=[o['id'] for o in rs if o['user_id']!=me];print(ids[0] if ids else '0')" 2>$null
if ($OTHER_ORDER_ID -ne "0" -and $OTHER_ORDER_ID) {
    $code = curl.exe -s -o NUL -w "%{http_code}" "$API/orders/$OTHER_ORDER_ID" -H "Authorization: Bearer $CTOKEN"
    if ($code -eq "404" -or $code -eq "403") {
        ok "Customer pidiendo pedido ajeno (id=$OTHER_ORDER_ID) -> $code (no leak)"
    } else {
        fail "Customer accedio pedido ajeno (id=$OTHER_ORDER_ID): $code"
    }
} else {
    # No hay otro user con pedidos; crear uno temporal para garantizar el test
    $TMP_EMAIL = "sec-test-$TS@cliente.com"
    curl.exe -s -o NUL -X POST "$API/auth/register" -H "Content-Type: application/json" `
        -d "{`"name`":`"SecTest`",`"email`":`"$TMP_EMAIL`",`"phone`":`"3000000001`",`"password`":`"SecTest1234*`"}"
    $TMP_LOGIN = do_login $TMP_EMAIL "SecTest1234*"
    $TMP_TOKEN = $TMP_LOGIN | json_field "access_token"
    curl.exe -s -o NUL -X POST "$API/cart/items" `
        -H "Authorization: Bearer $TMP_TOKEN" `
        -H "Content-Type: application/json" `
        -d '{"variant_id":11,"quantity":1}'
    $TMP_CHK = curl.exe -s -X POST "$API/checkout" `
        -H "Authorization: Bearer $TMP_TOKEN" `
        -H "Content-Type: application/json" `
        -H "Idempotency-Key: sec-$TS" `
        -d "{`"delivery_name`":`"x`",`"delivery_address`":`"Calle 1 #1`",`"delivery_city`":`"Bogota`",`"billing_document`":`"1024`",`"contact_phone`":`"3001112233`",`"contact_email`":`"$TMP_EMAIL`"}"
    $TMP_ORDER_ID = $TMP_CHK | json_field "order_id"
    $code = curl.exe -s -o NUL -w "%{http_code}" "$API/orders/$TMP_ORDER_ID" -H "Authorization: Bearer $CTOKEN"
    if ($code -eq "404" -or $code -eq "403") {
        ok "Customer e2e pidiendo pedido ajeno (id=$TMP_ORDER_ID de $TMP_EMAIL) -> $code (no leak)"
    } else {
        fail "Customer e2e accedio pedido ajeno (id=$TMP_ORDER_ID): $code"
    }
}

# ── Rate limit en /auth/login ─────────────────────────────────────────────────
step "Rate limit en /auth/login"
$HITS = 0; $RATE_LIMITED = 0
for ($i = 1; $i -le 15; $i++) {
    $code = curl.exe -s -o NUL -w "%{http_code}" -X POST "$API/auth/login" `
        -H "Content-Type: application/json" `
        -d '{"email":"noexiste@nada.com","password":"x"}'
    if ($code -eq "503" -or $code -eq "429") { $RATE_LIMITED++ }
    $HITS++
}
if ($RATE_LIMITED -ge 1) { ok "Rate limit golpea: $RATE_LIMITED/$HITS rechazos (esperado >=1)" }
else                      { warn "No vimos rate limit; quiza el burst es alto. ($HITS intentos sin bloqueo)" }

# ── Logs del gateway no contienen tokens ──────────────────────────────────────
step "Logs del gateway no contienen tokens en claro"
$LOGS = docker compose logs --tail 200 api-gateway 2>&1
if ($LOGS -like "*eyJhbGciOiJIUzI1NiJ*") {
    fail "Logs del gateway contienen JWT en claro"
} else {
    ok "Logs del gateway no exponen JWTs"
}

# ── Redis no responde a HTTP ──────────────────────────────────────────────────
step "Puertos internos NO accesibles como HTTP desde el host"
$code = curl.exe -s -o NUL -w "%{http_code}" "http://localhost:6379/" --max-time 2 2>$null
if (-not $code -or $code -eq "000") {
    ok "Redis :6379 no responde a HTTP (correcto: protocolo TCP nativo)"
} else {
    warn "Redis devuelve HTTP $code (esperaba ningun HTTP)"
}

# ── Resumen ───────────────────────────────────────────────────────────────────
Write-Host "`n========================================"  -ForegroundColor Cyan
Write-Host "  Resumen: $PASS PASS   $FAIL FAIL" -ForegroundColor $(if ($FAIL -eq 0) {"Green"} else {"Red"})
Write-Host "========================================`n" -ForegroundColor Cyan
exit $(if ($FAIL -eq 0) {0} else {1})
