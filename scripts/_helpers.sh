#!/usr/bin/env bash
# ============================================================================
# Helpers compartidos entre scripts E2E y Chaos Engineering.
# ============================================================================
#
# Provee:
#   - Codigos ANSI para output coloreado (verde OK, rojo FAIL, azul step).
#   - Contadores globales PASS / FAIL para resumen al final del script.
#   - Funciones de assertion: assert_eq, assert_contains.
#   - Helpers HTTP: http_call (devuelve status_code), login (devuelve JSON).
#   - Funcion summary() que imprime el reporte final y exit 0/1 segun
#     haya habido fallos.
#
# Para usar en otros scripts:
#   . "$DIR/_helpers.sh"
#
# Variable de entorno:
#   API_BASE → URL base del API Gateway (default http://localhost/api)
# ============================================================================

# set -u: error si se usa una variable no definida (paranoia bash).
set -u

# ─── Codigos ANSI para output coloreado ───────────────────────────────────
COLOR_OK="\033[0;32m"
COLOR_ERR="\033[0;31m"
COLOR_WARN="\033[0;33m"
COLOR_BLUE="\033[0;34m"
COLOR_DIM="\033[0;90m"
COLOR_RESET="\033[0m"

# URL base del API Gateway. Por defecto apunta al gateway local del compose.
# Para correr contra un staging remoto: API_BASE=https://staging.example.com/api ./script.sh
API="${API_BASE:-http://localhost/api}"

# ─── Contadores globales para el reporte final ────────────────────────────
PASS=0
FAIL=0

# ─── Funciones de output ──────────────────────────────────────────────────
# ok / fail incrementan los contadores; info / warn no afectan el resultado.
ok()    { printf "  ${COLOR_OK}OK${COLOR_RESET}     %s\n" "$1"; PASS=$((PASS+1)); }
fail()  { printf "  ${COLOR_ERR}FAIL${COLOR_RESET}   %s\n" "$1"; FAIL=$((FAIL+1)); }
info()  { printf "  ${COLOR_DIM}info${COLOR_RESET}   %s\n" "$1"; }
warn()  { printf "  ${COLOR_WARN}WARN${COLOR_RESET}   %s\n" "$1"; }
step()  { printf "\n${COLOR_BLUE}>>> %s${COLOR_RESET}\n" "$1"; }

# ─── Assertions ────────────────────────────────────────────────────────────

# Verifica igualdad estricta de dos strings.
# Uso: assert_eq "$actual" "$esperado" "descripcion del check"
assert_eq() {
  local actual="$1"
  local expected="$2"
  local desc="$3"
  if [ "$actual" = "$expected" ]; then
    ok "$desc (esperado=$expected actual=$actual)"
  else
    fail "$desc (esperado=$expected actual=$actual)"
  fi
}

# Verifica que un string contenga otro (substring).
# Util para validar fragmentos de JSON sin parsear todo el documento.
assert_contains() {
  local haystack="$1"
  local needle="$2"
  local desc="$3"
  if echo "$haystack" | grep -q "$needle"; then
    ok "$desc"
  else
    fail "$desc -- '$needle' no encontrado en respuesta"
  fi
}

# ─── Helpers HTTP ─────────────────────────────────────────────────────────

# Hace una llamada HTTP y devuelve solo el status code por stdout. El body
# queda en /tmp/td_body para inspeccion posterior.
# Uso: http_call POST $API/checkout -H "Content-Type: application/json" -d "$body"
http_call() {
  local method="$1"; shift
  local url="$1"; shift
  curl -s -o /tmp/td_body -w "%{http_code}" -X "$method" "$url" "$@"
}

# Login helper: devuelve el JSON completo de la respuesta de /auth/login.
# El caller extrae fields con `extract_field` (ej. access_token).
login() {
  local email="$1"
  local password="$2"
  curl -s -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}"
}

# Extrae un campo de un JSON via Python (mas confiable que jq que no siempre
# esta instalado). Lee JSON de stdin y escribe el valor del campo a stdout.
# Uso: TOKEN=$(echo "$LOGIN_RESPONSE" | extract_field access_token)
extract_field() {
  python -c "import sys,json;d=json.load(sys.stdin);print(d.get('$1',''))" 2>/dev/null
}

# ─── Resumen final ───────────────────────────────────────────────────────
# Imprime PASS/FAIL totales con colores y devuelve exit code 0 si todo PASS,
# 1 si hubo algun FAIL. Asi el script termina con codigo correcto para CI.
summary() {
  printf "\n"
  printf "${COLOR_BLUE}========================================${COLOR_RESET}\n"
  printf "  Resumen: ${COLOR_OK}%d PASS${COLOR_RESET}   ${COLOR_ERR}%d FAIL${COLOR_RESET}\n" "$PASS" "$FAIL"
  printf "${COLOR_BLUE}========================================${COLOR_RESET}\n"
  [ "$FAIL" = "0" ]
}
