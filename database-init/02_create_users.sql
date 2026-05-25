-- Crea un usuario por microservicio con permisos limitados a su esquema.
-- Materializa el patron Database per Service en su variante logica (un solo MySQL,
-- pero credenciales y GRANT separados por servicio para que ningun servicio pueda
-- leer ni escribir en la base de otro).

CREATE USER IF NOT EXISTS 'auth_user'@'%'      IDENTIFIED BY 'auth_pass';
CREATE USER IF NOT EXISTS 'catalog_user'@'%'   IDENTIFIED BY 'catalog_pass';
CREATE USER IF NOT EXISTS 'inventory_user'@'%' IDENTIFIED BY 'inventory_pass';
CREATE USER IF NOT EXISTS 'commerce_user'@'%'  IDENTIFIED BY 'commerce_pass';
CREATE USER IF NOT EXISTS 'payments_user'@'%'  IDENTIFIED BY 'payments_pass';

GRANT ALL PRIVILEGES ON auth_db.*      TO 'auth_user'@'%';
GRANT ALL PRIVILEGES ON catalog_db.*   TO 'catalog_user'@'%';
GRANT ALL PRIVILEGES ON inventory_db.* TO 'inventory_user'@'%';
GRANT ALL PRIVILEGES ON commerce_db.*  TO 'commerce_user'@'%';
GRANT ALL PRIVILEGES ON payments_db.*  TO 'payments_user'@'%';

FLUSH PRIVILEGES;
