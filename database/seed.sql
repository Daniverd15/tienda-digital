USE tienda_digital;

INSERT INTO users (id, name, email, phone, password_hash, role, active) VALUES
(1, 'Administrador Tienda', 'admin@tienda.com', '3001112233', 'pbkdf2_sha256$260000$admin-seed-salt$ZXRvy8IfnUX3rekn/Vv1d4cMQ9lU8KudGgzQoo+ezHY=', 'admin', TRUE),
(2, 'Cliente Demo', 'cliente@tienda.com', '3002223344', 'pbkdf2_sha256$260000$customer-seed-salt$BIKHOgXd+/IjEsI1CklyQ8Xm7XyaTCb1TW6ianCDF8U=', 'customer', TRUE);

INSERT INTO store_settings (id, commercial_name, logo_url, primary_color, secondary_color, banner_url, contact_email, contact_phone, currency, stock_threshold) VALUES
(1, 'Distrito Urbano', 'https://images.unsplash.com/photo-1523381294911-8d3cead13475', '#1f7a5c', '#f4b942', 'https://images.unsplash.com/photo-1441986300917-64674bd600d8', 'contacto@tienda.com', '6015550101', 'COP', 5);

INSERT INTO informative_messages (id, title, content, type, active, start_date, end_date) VALUES
(1, 'Envio local', 'Compras aprobadas antes de las 3 p.m. se preparan el mismo dia habil.', 'info', TRUE, '2026-01-01', '2026-12-31'),
(2, 'Pago simulado', 'La pasarela local permite probar estados aprobado, rechazado y pendiente.', 'warning', TRUE, '2026-01-01', '2026-12-31');

INSERT INTO categories (id, name, description, active, archived) VALUES
(1, 'Ropa', 'Prendas basicas y urbanas para uso diario.', TRUE, FALSE),
(2, 'Accesorios', 'Complementos para estilo casual.', TRUE, FALSE),
(3, 'Calzado', 'Tenis y zapatos deportivos.', TRUE, FALSE);

INSERT INTO products (id, category_id, name, description, long_description, base_price, published, archived, image_url) VALUES
(1, 1, 'Camiseta basica', 'Camiseta suave de algodon.', 'Camiseta basica de corte regular con tejido respirable, pensada para uso diario.', 45000, TRUE, FALSE, 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab'),
(2, 2, 'Gorra urbana', 'Gorra ajustable azul.', 'Gorra urbana con visera curva, cierre ajustable y costuras reforzadas.', 38000, TRUE, FALSE, 'https://images.unsplash.com/photo-1521369909029-2afed882baee'),
(3, 3, 'Tenis deportivos', 'Tenis comodos para caminar.', 'Tenis deportivos con suela flexible y amortiguacion basica para actividad diaria.', 160000, TRUE, FALSE, 'https://images.unsplash.com/photo-1542291026-7eec264c27ff');

INSERT INTO product_images (product_id, image_url, alt_text) VALUES
(1, 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab', 'Camiseta basica negra'),
(1, 'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c', 'Camiseta basica en perchero'),
(2, 'https://images.unsplash.com/photo-1521369909029-2afed882baee', 'Gorra urbana azul'),
(3, 'https://images.unsplash.com/photo-1542291026-7eec264c27ff', 'Tenis deportivos rojos');

INSERT INTO product_variants (id, product_id, sku, color, size, custom_attribute, cost, price, stock, reserved_stock, active) VALUES
(1, 1, 'CAM-NEG-M', 'negro', 'M', NULL, 21000, 45000, 35, 0, TRUE),
(2, 1, 'CAM-BLA-L', 'blanco', 'L', NULL, 21000, 47000, 4, 0, TRUE),
(3, 2, 'GOR-AZU-U', 'azul', NULL, 'ajustable', 18000, 38000, 0, 0, TRUE),
(4, 3, 'TEN-40', NULL, '40', NULL, 90000, 160000, 12, 0, TRUE),
(5, 3, 'TEN-42', NULL, '42', NULL, 90000, 165000, 3, 0, TRUE);

INSERT INTO inventory_movements (variant_id, movement_type, quantity, reason, user_id) VALUES
(1, 'entrada', 35, 'Inventario inicial', 1),
(2, 'entrada', 4, 'Inventario inicial cercano a umbral', 1),
(3, 'ajuste', 1, 'Variante sin stock visible', 1),
(4, 'entrada', 12, 'Inventario inicial', 1),
(5, 'entrada', 3, 'Inventario inicial cercano a umbral', 1);

INSERT INTO carts (id, user_id, status) VALUES
(1, 2, 'open');

INSERT INTO orders (id, order_code, user_id, status, payment_status, subtotal, additional_costs, discount, total, delivery_name, delivery_address, delivery_city, billing_document, contact_phone, contact_email) VALUES
(1, 'TD-SEED-ENTREGADO', 2, 'entregado', 'aprobado', 45000, 7000, 0, 52000, 'Cliente Demo', 'Calle 10 # 20-30', 'Bucaramanga', 'CC123', '3002223344', 'cliente@tienda.com'),
(2, 'TD-SEED-PENDIENTE', 2, 'pendiente_pago', 'pendiente', 38000, 7000, 0, 45000, 'Cliente Demo', 'Calle 10 # 20-30', 'Bucaramanga', 'CC123', '3002223344', 'cliente@tienda.com'),
(3, 'TD-SEED-PREPARACION', 2, 'preparacion', 'aprobado', 160000, 7000, 10000, 157000, 'Cliente Demo', 'Calle 10 # 20-30', 'Bucaramanga', 'CC123', '3002223344', 'cliente@tienda.com');

INSERT INTO order_items (order_id, variant_id, product_name, variant_description, quantity, unit_price, total) VALUES
(1, 1, 'Camiseta basica', 'negro / M', 1, 45000, 45000),
(2, 3, 'Gorra urbana', 'azul / ajustable', 1, 38000, 38000),
(3, 4, 'Tenis deportivos', '40', 1, 160000, 160000);

INSERT INTO payments (order_id, provider, transaction_reference, status, amount, response_message) VALUES
(1, 'SimuladorLocal', 'SIM-SEED-001', 'aprobado', 52000, 'Pago aprobado por pasarela simulada.'),
(2, 'SimuladorLocal', 'SIM-SEED-002', 'pendiente', 45000, 'Pago pendiente de confirmacion simulada.'),
(3, 'SimuladorLocal', 'SIM-SEED-003', 'aprobado', 157000, 'Pago aprobado por pasarela simulada.');

INSERT INTO notifications (user_id, order_id, title, message, `read`) VALUES
(2, 1, 'Pedido entregado', 'Tu pedido TD-SEED-ENTREGADO fue entregado y puedes crear una resena.', FALSE),
(2, 2, 'Pago pendiente', 'Tu pedido TD-SEED-PENDIENTE esta pendiente de confirmacion.', FALSE);

INSERT INTO reviews (user_id, product_id, order_id, rating, comment, approved) VALUES
(2, 1, 1, 5, 'La camiseta llego rapido y la tela es comoda.', TRUE);

INSERT INTO employees (id, name, document, position, salary, employment_status) VALUES
(1, 'Administrador de tienda', 'EMP001', 'Administrador', 2500000, 'active'),
(2, 'Auxiliar logistico', 'EMP002', 'Auxiliar logistico', 1600000, 'active');

INSERT INTO expenses (expense_type, description, amount, observation, expense_date, created_by) VALUES
('Arriendo', 'Arriendo local administrativo', 1200000, 'Costo mensual fijo', '2026-05-01', 1),
('Servicios', 'Servicios publicos e internet', 350000, 'Operacion mensual', '2026-05-02', 1),
('Publicidad', 'Campana digital local', 500000, 'Pauta redes sociales', '2026-05-03', 1);

INSERT INTO audit_logs (user_id, action, entity, entity_id, previous_value, new_value) VALUES
(1, 'seed_database', 'system', 'seed', NULL, '{"status":"initial data loaded"}');

INSERT INTO system_logs (level, message, context) VALUES
('INFO', 'Base de datos inicializada con datos academicos de prueba.', '{"source":"seed.sql"}');

