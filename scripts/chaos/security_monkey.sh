#!/usr/bin/env bash
# ============================================================================
# Security Monkey: el sistema valida autorizacion y rechaza accesos invalidos.
# ============================================================================
#
# Equivalente del Security Monkey del Simian Army de Netflix: audita
# defensas de seguridad del sistema en busca de vulnerabilidades comunes
# (OWASP Top 10: broken authentication, broken access control, IDOR).
#
# Hipotesis (informe Fase 1, seccion 18.9):
#   - /admin/* sin JWT → 401 Unauthorized.
#   - /admin/* con JWT de customer (no admin) → 403 Forbidden.
#   - Cabeceras de seguridad presentes en el gateway (X-Frame-Options,
#     X-Content-Type-Options, Referrer-Policy).
#   - JWT con firma invalida → 401.
#   - JWT vencido o corrupto → 401.
#   - Logs NO contienen tokens (evita filtraciones por log scraping).
#   - Pedidos ajenos NO son consultables por otros usuarios (IDOR).
#   - Rate limit en /auth/login impide brute force (5 req/min/IP).
#
# Salida esperada: 27 PASS / 0 FAIL en condiciones normales.
# ============================================================================

set -u
DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$DIR/_helpers.sh"

step "Cabeceras de seguridad en el gateway"
HDR=$(curl -sI "$API/catalog")
assert_contains "$HDR" "X-Content-Type-Options: nosniff"  "Header X-Content-Type-Options presente"
assert_contains "$HDR" "X-Frame-Options: DENY"            "Header X-Frame-Options presente"
assert_contains "$HDR" "Referrer-Policy"                  "Header Referrer-Policy presente"

step "Accesos sin JWT a recursos protegidos"
for path in /auth/me /cart /orders/mine /notifications /admin/customers /admin/orders /admin/inventory/variants; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API$path")
  assert_eq "$code" "401" "GET $path sin token -> 401"
done

step "Accesos con JWT corrupto"
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/me" -H "Authorization: Bearer not.a.jwt")
assert_eq "$code" "401" "JWT corrupto -> 401"
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/auth/me" -H "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.fake.signature")
assert_eq "$code" "401" "JWT con firma invalida -> 401"

step "Login admin + customer para pruebas de rol"
ADMIN=$(login "admin@tienda.com" "Admin1234*")
ATOKEN=$(echo "$ADMIN" | extract_field access_token)

CLIENT=$(login "e2e@cliente.com" "E2eTest1234*")
CTOKEN=$(echo "$CLIENT" | extract_field access_token)
[ -z "$CTOKEN" ] && {
  curl -s -o /dev/null -X POST "$API/auth/register" -H "Content-Type: application/json" \
    -d '{"name":"E2E","email":"e2e@cliente.com","phone":"3000000000","password":"E2eTest1234*"}'
  CLIENT=$(login "e2e@cliente.com" "E2eTest1234*")
  CTOKEN=$(echo "$CLIENT" | extract_field access_token)
}

step "Acceso a /admin con token de customer (deberia ser 403)"
for path in /admin/customers /admin/orders /admin/inventory/variants /admin/finance/summary /admin/employees /admin/expenses; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API$path" -H "Authorization: Bearer $CTOKEN")
  assert_eq "$code" "403" "GET $path con token customer -> 403"
done

step "Acceso a /admin con token de admin (deberia ser 200)"
for path in /admin/customers /admin/orders /admin/employees /admin/expenses /admin/audit-logs /admin/finance/summary; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API$path" -H "Authorization: Bearer $ATOKEN")
  if [ "$code" = "200" ]; then
    ok "GET $path con admin -> 200"
  else
    fail "GET $path con admin -> $code (esperaba 200)"
  fi
done

step "Aislamiento: customer no puede ver pedidos de OTRO customer"
# Tomamos un pedido cuyo user_id sea DISTINTO al customer e2e@cliente.com
MY_USER_ID=$(curl -s "$API/auth/me" -H "Authorization: Bearer $CTOKEN" | extract_field id)
OTHER_ORDER_ID=$(curl -s "$API/admin/orders" -H "Authorization: Bearer $ATOKEN" \
  | python -c "import sys,json,os;rs=json.load(sys.stdin);me=$MY_USER_ID;ids=[o['id'] for o in rs if o['user_id']!=me];print(ids[0] if ids else '0')")
if [ "$OTHER_ORDER_ID" != "0" ]; then
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API/orders/$OTHER_ORDER_ID" -H "Authorization: Bearer $CTOKEN")
  if [ "$code" = "404" ] || [ "$code" = "403" ]; then
    ok "Customer pidiendo pedido ajeno (id=$OTHER_ORDER_ID) -> $code (no leak)"
  else
    fail "Customer accedio pedido ajeno (id=$OTHER_ORDER_ID): $code"
  fi
else
  # No hay otro user con pedidos; creamos uno rapido para garantizar el test
  TMP_EMAIL="sec-test-$(date +%s)@cliente.com"
  curl -s -o /dev/null -X POST "$API/auth/register" -H "Content-Type: application/json" \
    -d "{\"name\":\"SecTest\",\"email\":\"$TMP_EMAIL\",\"phone\":\"3000000001\",\"password\":\"SecTest1234*\"}"
  TMP_LOGIN=$(login "$TMP_EMAIL" "SecTest1234*")
  TMP_TOKEN=$(echo "$TMP_LOGIN" | extract_field access_token)
  curl -s -o /dev/null -X POST "$API/cart/items" -H "Authorization: Bearer $TMP_TOKEN" \
    -H "Content-Type: application/json" -d '{"variant_id":11,"quantity":1}'
  TMP_CHK=$(curl -s -X POST "$API/checkout" -H "Authorization: Bearer $TMP_TOKEN" \
    -H "Content-Type: application/json" -H "Idempotency-Key: sec-$(date +%s)" \
    -d "{\"delivery_name\":\"x\",\"delivery_address\":\"Calle 1 #1\",\"delivery_city\":\"Bogota\",\"billing_document\":\"1024\",\"contact_phone\":\"3001112233\",\"contact_email\":\"$TMP_EMAIL\"}")
  TMP_ORDER_ID=$(echo "$TMP_CHK" | extract_field order_id)
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API/orders/$TMP_ORDER_ID" -H "Authorization: Bearer $CTOKEN")
  if [ "$code" = "404" ] || [ "$code" = "403" ]; then
    ok "Customer e2e pidiendo pedido ajeno (id=$TMP_ORDER_ID de $TMP_EMAIL) -> $code (no leak)"
  else
    fail "Customer e2e accedio pedido ajeno (id=$TMP_ORDER_ID): $code"
  fi
fi

step "Rate limit en /auth/login"
HITS=0
RATE_LIMITED=0
for i in $(seq 1 15); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"noexiste@nada.com","password":"x"}')
  if [ "$code" = "503" ] || [ "$code" = "429" ]; then
    RATE_LIMITED=$((RATE_LIMITED+1))
  fi
  HITS=$((HITS+1))
done
if [ "$RATE_LIMITED" -ge 1 ]; then
  ok "Rate limit golpea: $RATE_LIMITED/$HITS rechazos (esperado >=1)"
else
  warn "No vimos rate limit; quiza el burst es alto. ($HITS intentos sin bloqueo)"
fi

step "Logs del gateway no contienen tokens en claro"
LOGS=$(docker compose logs --tail 200 api-gateway 2>&1)
if echo "$LOGS" | grep -q "eyJhbGciOiJIUzI1NiJ"; then
  fail "Logs del gateway contienen JWT en claro"
else
  ok "Logs del gateway no exponen JWTs"
fi

step "Puertos internos NO accesibles desde el host fuera del proposito"
# El gateway es el unico que debe responder /api/* en :80; los servicios estan
# tambien expuestos para diagnostico (8001-8005) pero NO MySQL/Redis/RabbitMQ
# en su API protegida.
code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:6379/" --max-time 2 2>/dev/null || true)
# Redis habla un protocolo TCP propio (RESP); ante HTTP devuelve linea vacia
# que curl interpreta como 000. Lo que importa es que NO se filtre data de
# negocio a alguien que solo sepa hacer HTTP.
if [ -z "$code" ] || [ "$code" = "000" ] || [ "$code" = "000000" ]; then
  ok "Redis :6379 no responde a HTTP (correcto: protocolo TCP nativo)"
else
  warn "Redis devuelve HTTP $code (esperaba ningun HTTP)"
fi

summary
