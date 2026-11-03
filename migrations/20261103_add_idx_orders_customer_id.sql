-- Safe migration SQL
SET statement_timeout = '30s';
SET lock_timeout = '5s';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_customer_id ON orders (customer_id) INCLUDE (order_id, status);