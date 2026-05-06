# Instalacion

## Requisitos

- Docker Desktop con Docker Compose.
- Python 3.12 o superior.
- Node.js 20 o superior.
- Git.

## Base De Datos

```powershell
cd tienda-digital
docker compose up -d
```

Docker ejecuta `database/schema.sql` y `database/seed.sql` al crear el volumen por primera vez.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

API local: `http://localhost:8000`.

## Frontend

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

App local: `http://localhost:5173`.

## Respaldo

```powershell
.\database\backup_mysql.ps1
```

El script usa `mysqldump`; pedir la contrasena configurada en Docker Compose: `tienda_password`.

