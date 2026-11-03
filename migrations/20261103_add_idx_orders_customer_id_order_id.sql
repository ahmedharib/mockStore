-- Safe migration SQL
SET statement_timeout = '30s';
SET lock_timeout = '5s';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_customer_id_order_id ON orders (customer_id, order_id) INCLUDE (status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_order_items_order_id ON order_items (order_id) INCLUDE (product_id, quantity);