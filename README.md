# Tienda Digital Scrum

Aplicacion academica de tienda digital construida incrementalmente para evidenciar requisitos SRS, trabajo Scrum y commits por requisito.

## Descripcion

La solucion permite autenticar clientes y administradores, navegar catalogo, buscar productos, gestionar carrito, hacer checkout, simular pagos, crear pedidos, descontar inventario, administrar catalogo, finanzas, configuracion, mensajes y resenas validadas por compra entregada.

## Stack

- Frontend: React, Vite, React Router, Axios, CSS responsive.
- Backend: FastAPI, SQLAlchemy, Pydantic, JWT, Passlib/bcrypt, PyMySQL.
- Base de datos: MySQL 8 con `database/schema.sql` y `database/seed.sql`.
- Pruebas: Pytest.
- Infra local: Docker Compose para MySQL.

## Integrantes Y Roles

- Daniel Villamizar: frontend.
- Santiago Perez: backend, base de datos, APIs y logica de negocio.
- Tomas Urieles: Scrum Master, integracion, documentacion, pruebas, configuracion y RNF.

## Requisitos Cubiertos

Se implementan RF-01 a RF-09 y RNF-01 a RNF-03. La trazabilidad completa esta en `docs/backlog-commits.md`.

## Instalacion Desde Cero

1. Instalar Docker Desktop, Python 3.12+ y Node.js.
2. Entrar al proyecto:

```powershell
cd tienda-digital
```

3. Levantar MySQL:

```powershell
docker compose up -d
```

4. Preparar backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

5. Preparar frontend en otra terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

6. Abrir `http://localhost:5173`.

## Credenciales De Prueba

- Administrador: `admin@tienda.com` / `Admin123*`
- Cliente: `cliente@tienda.com` / `Cliente123*`

Las contrasenas seed estan guardadas con hash PBKDF2 compatible con el verificador del backend. Los usuarios nuevos se guardan con Passlib/bcrypt.

## Comandos Principales

```powershell
docker compose up -d
docker compose down
cd backend; uvicorn main:app --reload
cd frontend; npm.cmd run dev
cd backend; pytest
cd backend; python -m app.utils.load_check --url http://localhost:8000/products --requests 20 --workers 5
.\database\backup_mysql.ps1
git log --oneline --decorate
```

## Notas De Entorno

En la maquina usada para generar este entregable se detecto Git y Node. Python y Docker no estaban disponibles, por lo que la verificacion completa requiere instalarlos o habilitarlos localmente.

