#!/usr/bin/env bash
# Helpers compartidos entre scripts E2E y Chaos.

set -u

# Codigos ANSI para output
COLOR_OK="\033[0;32m"
COLOR_ERR="\033[0;31m"
COLOR_WARN="\033[0;33m"
COLOR_BLUE="\033[0;34m"
COLOR_DIM="\033[0;90m"
COLOR_RESET="\033[0m"

API="${API_BASE:-http://localhost/api}"

# Resultados
PASS=0
FAIL=0

ok()    { printf "  ${COLOR_OK}OK${COLOR_RESET}     %s\n" "$1"; PASS=$((PASS+1)); }
fail()  { printf "  ${COLOR_ERR}FAIL${COLOR_RESET}   %s\n" "$1"; FAIL=$((FAIL+1)); }
info()  { printf "  ${COLOR_DIM}info${COLOR_RESET}   %s\n" "$1"; }
warn()  { printf "  ${COLOR_WARN}WARN${COLOR_RESET}   %s\n" "$1"; }
step()  { printf "\n${COLOR_BLUE}>>> %s${COLOR_RESET}\n" "$1"; }

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

# Hace POST/GET y extrae status code + cuerpo.
# Uso: http_status_and_body METHOD URL [HEADERS]... -d BODY
http_call() {
  local method="$1"; shift
  local url="$1"; shift
  curl -s -o /tmp/td_body -w "%{http_code}" -X "$method" "$url" "$@"
}

login() {
  local email="$1"
  local password="$2"
  curl -s -X POST "$API/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}"
}

extract_field() {
  python -c "import sys,json;d=json.load(sys.stdin);print(d.get('$1',''))" 2>/dev/null
}

summary() {
  printf "\n"
  printf "${COLOR_BLUE}========================================${COLOR_RESET}\n"
  printf "  Resumen: ${COLOR_OK}%d PASS${COLOR_RESET}   ${COLOR_ERR}%d FAIL${COLOR_RESET}\n" "$PASS" "$FAIL"
  printf "${COLOR_BLUE}========================================${COLOR_RESET}\n"
  [ "$FAIL" = "0" ]
}
