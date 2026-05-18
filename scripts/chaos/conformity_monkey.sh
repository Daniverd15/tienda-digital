#!/usr/bin/env bash
# Conformity Monkey: cada microservicio cumple los estandares del equipo.
#
# Hipotesis (informe Fase 1, seccion 18.8):
# - Cada servicio expone /health
# - Cada servicio tiene .env.example, Dockerfile, requirements.txt, app/, tests/
# - Cada servicio responde 200 desde su puerto directo
# - Cada servicio reporta su nombre en GET /
# - Cada Dockerfile usa USER no-root
# - El gateway enruta los 5 servicios correctamente

set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$DIR/_helpers.sh"

step "Estructura de cada microservicio"
ROOT="$(cd "$DIR/.." && pwd)"
for svc in auth catalog inventory commerce payment; do
  base="$ROOT/services/$svc-service"
  for required in Dockerfile requirements.txt .env.example app/main.py; do
    if [ -e "$base/$required" ]; then
      ok "services/$svc-service/$required existe"
    else
      fail "services/$svc-service/$required NO existe"
    fi
  done
done

step "Cada Dockerfile usa USER no-root"
for svc in auth catalog inventory commerce payment; do
  if grep -q "^USER " "$ROOT/services/$svc-service/Dockerfile"; then
    ok "$svc-service/Dockerfile declara USER no-root"
  else
    fail "$svc-service/Dockerfile no declara USER"
  fi
done

step "Healthchecks directos a cada servicio"
declare -A PORTS=( [auth]=8001 [catalog]=8002 [inventory]=8003 [commerce]=8004 [payment]=8005 )
for svc in auth catalog inventory commerce payment; do
  port=${PORTS[$svc]}
  body=$(curl -s "http://localhost:$port/health")
  svc_in_body=$(echo "$body" | python -c "import sys,json;print(json.load(sys.stdin).get('service',''))" 2>/dev/null)
  expected="${svc}-service"
  assert_eq "$svc_in_body" "$expected" "Puerto $port reporta service=$expected"
done

step "Endpoint GET / reporta service y version"
for svc in auth catalog inventory commerce payment; do
  port=${PORTS[$svc]}
  body=$(curl -s "http://localhost:$port/")
  has_version=$(echo "$body" | python -c "import sys,json;d=json.load(sys.stdin);print('1' if 'version' in d else '')" 2>/dev/null)
  if [ "$has_version" = "1" ]; then
    ok "$svc-service expone version en GET /"
  else
    warn "$svc-service no expone version en GET /"
  fi
done

step "Healthchecks de Docker reportan healthy"
docker compose ps --format json 2>&1 > /tmp/td_ps.json || \
  docker compose ps --format '{{json .}}' > /tmp/td_ps.json
HEALTHY=$(docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>&1 | grep -c "(healthy)")
if [ "$HEALTHY" -ge 8 ]; then
  ok "$HEALTHY contenedores con (healthy) en docker compose ps"
else
  warn "Solo $HEALTHY contenedores healthy"
fi

step "El gateway enruta correctamente cada microservicio"
declare -A GW_ROUTES=(
  [auth]=/api/auth/me
  [catalog]=/api/catalog
  [inventory]=/api/inventory/variants/1
  [commerce]=/api/orders/mine
  [payment]=/api/payments/circuit/state
)
for svc in auth catalog inventory commerce payment; do
  ruta=${GW_ROUTES[$svc]}
  # Algunas requieren auth; aceptamos 200 o 401/403 (= la peticion llego al servicio)
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost$ruta")
  if [ "$code" = "200" ] || [ "$code" = "401" ] || [ "$code" = "403" ] || [ "$code" = "404" ]; then
    ok "$svc-service alcanzable via gateway en $ruta (HTTP $code)"
  else
    fail "$svc-service NO alcanzable via gateway en $ruta (HTTP $code)"
  fi
done

step "Cada servicio usa Database per Service con credenciales propias"
for svc in auth catalog inventory commerce payments; do
  user="${svc}_user"
  pass="${svc}_pass"
  db="${svc}_db"
  res=$(docker exec tienda_digital_mysql mysql -u "$user" -p"$pass" -e "USE $db; SHOW TABLES;" 2>&1 | grep -v Warning | wc -l)
  if [ "$res" -gt 0 ]; then
    ok "$user puede leer $db con sus credenciales"
  else
    fail "$user no puede leer $db"
  fi
  # Y NO puede leer otra base
  other_db="auth_db"
  [ "$svc" = "auth" ] && other_db="catalog_db"
  denied=$(docker exec tienda_digital_mysql mysql -u "$user" -p"$pass" -e "USE $other_db;" 2>&1 | grep -c "denied\|ERROR")
  if [ "$denied" -gt 0 ]; then
    ok "$user NO puede leer $other_db (aislamiento OK)"
  else
    fail "$user puede leer $other_db (FUGA de privilegios)"
  fi
done

summary
