# Instalacion

Instrucciones para levantar la arquitectura de microservicios localmente.

## Requisitos

- Docker Desktop con Docker Compose v2
- Node.js 20 o superior (solo para el frontend en modo dev)
- Git
- 4 GB de RAM libres y los puertos 80, 1025, 3306, 6379, 8001-8005, 8025, 8080, 9000 sin uso

## 1. Clonar el repositorio

```powershell
git clone <url-del-repo> tienda-digital
cd tienda-digital
```

## 2. Levantar los 12 contenedores

```powershell
docker compose up --build -d
docker compose ps
```

El primer arranque tarda ~30s porque MySQL ejecuta los scripts iniciales:

1. `database/schema.sql` y `database/seed.sql` (esquema y datos del monolito en `tienda_digital`)
2. `database-init/01_create_databases.sql` (crea `auth_db`, `catalog_db`, `inventory_db`, `commerce_db`, `payments_db`)
3. `database-init/02_create_users.sql` (crea un usuario por servicio con `GRANT` exclusivo)

Los servicios inician con `lifespan` async y `Base.metadata.create_all`, asi que
no requieren migraciones Alembic manuales en el arranque inicial.

## 3. Verificar healthchecks

```powershell
curl http://localhost/health/gateway
curl http://localhost/health/auth
curl http://localhost/health/catalog
curl http://localhost/health/inventory
curl http://localhost/health/commerce
curl http://localhost/health/payment
```

Los 6 deben responder `{"status":"ok",...}`. Si alguno responde `degraded`,
revisar logs con `docker compose logs <servicio>`.

## 4. Frontend (modo desarrollo)

```powershell
cd frontend
npm install
npm run dev
```

App: <http://localhost:5173>. Usa `VITE_API_URL=http://localhost/api` (gateway).

## 5. Credenciales seed

| Rol | Email | Password |
|---|---|---|
| Administrador | `admin@tienda.com` | `Admin1234*` |

Los clientes se crean por `POST /api/auth/register` con politica de contrasena
fuerte (>=8, mayuscula, minuscula, digito, simbolo).

## Herramientas auxiliares incluidas

- **phpMyAdmin** (<http://localhost:8080>): inspeccion de los 5 esquemas + el esquema legacy
- **Mailhog UI** (<http://localhost:8025>): correos transaccionales (bienvenida, transiciones de pedido)
- **payment-mock** (<http://localhost:9000>): pasarela simulada con 4 escenarios

## Comandos comunes

```powershell
# Logs en vivo
docker compose logs -f commerce-service

# Reiniciar un servicio
docker compose restart payment-service

# Reconstruir tras cambios en codigo
docker compose up -d --build catalog-service

# Acceder a MySQL como root
docker compose exec mysql mysql -uroot -proot_password

# Detener todo
docker compose down

# Detener y borrar datos (ATENCION: pierde MySQL)
docker compose down -v
```

## Backup de MySQL

```powershell
.\database\backup_mysql.ps1
```

El script usa `mysqldump`. Contrasena root configurada en
`docker-compose.yml`: `root_password`.

## Smoke E2E + Chaos Engineering

Una vez los healthchecks estan en verde, validar la arquitectura completa con
los 5 scripts (133 verificaciones automatizadas):

```bash
bash scripts/e2e/flujo_completo.sh             # 34 PASS
bash scripts/chaos/conformity_monkey.sh        # 51 PASS
bash scripts/chaos/security_monkey.sh          # 27 PASS
bash scripts/chaos/chaos_monkey_inventory.sh   # 12 PASS
bash scripts/chaos/latency_monkey_payment.sh   #  9 PASS
```

En PowerShell sin Git Bash, los scripts se pueden ejecutar dentro del contenedor
de Auth Service (que tiene bash):

```powershell
docker compose exec -T auth-service bash -c "cd /scripts && bash e2e/flujo_completo.sh"
```

## Monolito legacy (opcional)

El monolito Fase 1 se preserva en `backend_legacy_monolito/`. No se levanta con
`docker compose up`. Para correrlo aisladamente como referencia historica:

```powershell
cd backend_legacy_monolito
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --port 8000
```

Apunta al esquema `tienda_digital` (el mismo MySQL del compose).
