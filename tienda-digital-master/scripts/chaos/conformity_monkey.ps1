# =============================================================================
# Conformity Monkey: cada microservicio cumple los estandares del equipo.
# Equivalente a conformity_monkey.sh para PowerShell en Windows.
# Uso: cd tienda-digital-master; .\scripts\chaos\conformity_monkey.ps1
# Requiere: docker compose up -d (todos los contenedores corriendo)
# Salida esperada: 51 PASS / 0 FAIL en condiciones normales.
# =============================================================================
$API = "http://localhost/api"
$PASS = 0; $FAIL = 0

function ok($msg)   { Write-Host "  OK     $msg" -ForegroundColor Green;  $script:PASS++ }
function fail($msg) { Write-Host "  FAIL   $msg" -ForegroundColor Red;    $script:FAIL++ }
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

# Raiz del repositorio: 2 niveles arriba de scripts/chaos/
$ROOT = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

# ── Estructura de cada microservicio ─────────────────────────────────────────
step "Estructura de cada microservicio"
foreach ($svc in @("auth","catalog","inventory","commerce","payment")) {
    $base = "$ROOT\services\$svc-service"
    foreach ($required in @("Dockerfile","requirements.txt",".env.example","app\main.py")) {
        if (Test-Path "$base\$required") { ok "services/$svc-service/$required existe" }
        else                              { fail "services/$svc-service/$required NO existe" }
    }
}

# ── Dockerfile declara USER no-root ───────────────────────────────────────────
step "Cada Dockerfile usa USER no-root"
foreach ($svc in @("auth","catalog","inventory","commerce","payment")) {
    $df = "$ROOT\services\$svc-service\Dockerfile"
    if (Select-String -Path $df -Pattern "^USER " -Quiet 2>$null) {
        ok "$svc-service/Dockerfile declara USER no-root"
    } else {
        fail "$svc-service/Dockerfile no declara USER"
    }
}

# ── Healthchecks directos a cada servicio ────────────────────────────────────
step "Healthchecks directos a cada servicio"
$PORTS = @{ auth=8001; catalog=8002; inventory=8003; commerce=8004; payment=8005 }
foreach ($svc in @("auth","catalog","inventory","commerce","payment")) {
    $port = $PORTS[$svc]
    $body = curl.exe -s "http://localhost:$port/health"
    $svc_in_body = $body | python -c "import sys,json;print(json.load(sys.stdin).get('service',''))" 2>$null
    $expected = "$svc-service"
    assert_eq $svc_in_body $expected "Puerto $port reporta service=$expected"
}

# ── GET / reporta version ─────────────────────────────────────────────────────
step "Endpoint GET / reporta service y version"
foreach ($svc in @("auth","catalog","inventory","commerce","payment")) {
    $port = $PORTS[$svc]
    $body = curl.exe -s "http://localhost:$port/"
    $has_version = $body | python -c "import sys,json;d=json.load(sys.stdin);print('1' if 'version' in d else '')" 2>$null
    if ($has_version -eq "1") { ok "$svc-service expone version en GET /" }
    else                       { warn "$svc-service no expone version en GET /" }
}

# ── Docker compose ps healthy ─────────────────────────────────────────────────
step "Healthchecks de Docker reportan healthy"
$ps_output = docker compose ps 2>&1
$HEALTHY = ($ps_output | Select-String -Pattern "\(healthy\)").Count
if ($HEALTHY -ge 8) { ok "$HEALTHY contenedores con (healthy) en docker compose ps" }
else                  { warn "Solo $HEALTHY contenedores healthy" }

# ── Gateway enruta correctamente ──────────────────────────────────────────────
step "El gateway enruta correctamente cada microservicio"
$GW_ROUTES = @{
    auth      = "/api/auth/me"
    catalog   = "/api/catalog"
    inventory = "/api/inventory/variants/1"
    commerce  = "/api/orders/mine"
    payment   = "/api/payments/circuit/state"
}
foreach ($svc in @("auth","catalog","inventory","commerce","payment")) {
    $ruta = $GW_ROUTES[$svc]
    $code = curl.exe -s -o NUL -w "%{http_code}" "http://localhost$ruta"
    if ($code -eq "200" -or $code -eq "401" -or $code -eq "403" -or $code -eq "404") {
        ok "$svc-service alcanzable via gateway en $ruta (HTTP $code)"
    } else {
        fail "$svc-service NO alcanzable via gateway en $ruta (HTTP $code)"
    }
}

# ── Database per Service ──────────────────────────────────────────────────────
step "Cada servicio usa Database per Service con credenciales propias"
foreach ($svc in @("auth","catalog","inventory","commerce","payments")) {
    $user = "${svc}_user"
    $pass = "${svc}_pass"
    $db   = "${svc}_db"
    $res  = docker exec tienda_digital_mysql mysql -u $user -p"$pass" -e "USE $db; SHOW TABLES;" 2>&1
    $lines = ($res | Where-Object { $_ -notmatch "Warning" }).Count
    if ($lines -gt 0) { ok "$user puede leer $db con sus credenciales" }
    else               { fail "$user no puede leer $db" }
    # Y NO puede leer otra base
    $other_db = "auth_db"
    if ($svc -eq "auth") { $other_db = "catalog_db" }
    $denied = docker exec tienda_digital_mysql mysql -u $user -p"$pass" -e "USE $other_db;" 2>&1
    $denied_count = ($denied | Select-String -Pattern "denied|ERROR").Count
    if ($denied_count -gt 0) { ok "$user NO puede leer $other_db (aislamiento OK)" }
    else                       { fail "$user puede leer $other_db (FUGA de privilegios)" }
}

# ── Resumen ───────────────────────────────────────────────────────────────────
Write-Host "`n========================================"  -ForegroundColor Cyan
Write-Host "  Resumen: $PASS PASS   $FAIL FAIL" -ForegroundColor $(if ($FAIL -eq 0) {"Green"} else {"Red"})
Write-Host "========================================`n" -ForegroundColor Cyan
exit $(if ($FAIL -eq 0) {0} else {1})
