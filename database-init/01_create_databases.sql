-- Crea los esquemas separados por microservicio.
-- Se ejecuta automaticamente cuando MySQL arranca por primera vez en un volumen vacio.
-- Si el volumen ya existe (caso del monolito previo), aplicar manualmente con:
--   docker compose exec mysql sh -c 'mysql -uroot -proot_password < /docker-entrypoint-initdb.d/01_create_databases.sql'

CREATE DATABASE IF NOT EXISTS auth_db      CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS catalog_db   CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS inventory_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS commerce_db  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS payments_db  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
