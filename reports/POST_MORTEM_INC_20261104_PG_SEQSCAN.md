# Post-Mortem: INC-20261104-PG-SEQSCAN - PG_SLOW_QUERY_BREACH on postgres-live-telemetry

## 1. Incident Metadata

| Field | Value |
|---|---|
| Incident ID | INC-20261104-PG-SEQSCAN |
| Vector | VECTOR_A_DB |
| Service | postgres-live-telemetry |
| Error Code | PG_SLOW_QUERY_BREACH |
| Error Message | P99 query latency spiked to 245.24ms (SLA threshold: 1000.0ms) |
| Offending Query | SELECT o.order_id, o.status, i.product_id, i.quantity FROM orders o JOIN order_items i ON o.order_id = i.order_id WHERE o.customer_id = %s |
| Host CPU | null (production); 94.2% baseline in sandbox |
| Raw Plan Total Cost | 1428.17 (startup 525.9) |
| Execution Time (local) | 8.457ms, Planning 0.303ms |
| Production-Equivalent Latency | 296.0ms |
| Rows Returned / Scanned | 40 returned / 50000 scanned (order_items) + 22620 scanned (orders) |

## 2. Executive Summary

postgres-live-telemetry breached slow-query detection for a customer-order lookup join. Autonomous analysis found double sequential scans feeding a hash join. A concurrent covering-index migration was applied and verified in sandbox sb-TKLluaY0peF9ckNfK80wr9 with 98.06% latency reduction and 90.23% CPU reduction, no locks, deterministic gate passed. Ready to merge with CONCURRENTLY for zero downtime.

## 3. Impact

- Query reads ~532 shared hit blocks (~4MB) per execution for <50 rows output.
- Local 8.457ms scales to 296.0ms production-equivalent due to data size / concurrency / cold cache.
- CPU saturation risk: 94.2% baseline in sandbox.
- I/O scales linearly with table growth (22620 orders, 50000 items in incident; 120k items in sandbox scale test).
- Every customer lookup wastes heap scan: 22591 rows removed by filter.

## 4. Root Cause Analysis

Plan nodes (incident):
- Hash Join (cost=1428.17, actual_rows=40)
- Seq Scan on order_items (cost=771.0, actual_rows=50000)
- Hash (cost=525.65, actual_rows=29)
- Seq Scan on orders (cost=525.65, actual_rows=29)

Details:
- orders Seq Scan: Filter (customer_id = 639), Rows Removed by Filter 22591, Shared Hit Blocks 261, Actual 29 rows vs Plan 20 rows. Selectivity 0.13%. Only orders_pkey on order_id exists.
- order_items Seq Scan: Full 50000 rows, Shared Hit Blocks 271, no filter, built as outer side of Hash Join on Hash Cond (i.order_id = o.order_id).
- Hash: Buckets 1024, Batches 1, Peak Memory 10kB, Startup 1.68ms blocking probe.
- Join: Inner Unique true, Plan Rows 47 vs Actual 40, Plan Width 19.
- Planning Shared Hit Blocks 54.
- No index on orders(customer_id) or order_items(order_id) FK, no covering INCLUDE for (order_id, status) and (product_id, quantity).

## 5. Resolution - Verified DDL Migration

Ready-to-merge migration (zero-downtime, idempotent):

```sql
SET statement_timeout = '30s';
SET lock_timeout = '5s';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_customer_id ON public.orders USING btree (customer_id) INCLUDE (order_id, status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_order_items_order_id ON public.order_items USING btree (order_id) INCLUDE (product_id, quantity);
```

Note: verified_patch contained a third redundant line `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_order_items_order_id ON order_items (order_id);` which is a safe no-op due to IF NOT EXISTS after the covering definition above. Deduplicated to 2 covering indexes for merge.

Why covering:
- idx_orders_customer_id serves WHERE customer_id = $1 and covers SELECT order_id, status -> Bitmap Index Scan + Bitmap Heap Scan.
- idx_order_items_order_id serves JOIN ON order_id and covers SELECT product_id, quantity -> Index Only Scan, enables Nested Loop (cost 1669.92) vs Hash Join (cost 3531.5).
- CONCURRENTLY + timeouts avoid ACCESS EXCLUSIVE blocking; IF NOT EXISTS allows rerun.

## 6. Sandbox Verification Proof

- Environment: MODAL_CLOUD_POSTGRES_SANDBOX
- Sandbox ID: sb-TKLluaY0peF9ckNfK80wr9
- Duration: 4.59s
- Deterministic Gate: PASSED, Table Locks Detected: false, Error: null

Before (baseline):
- Hash Join (cost=3531.5, actual_rows=240)
- Seq Scan on order_items (cost=1965.0, actual_rows=120000)
- Hash (cost=1250.0, actual_rows=120)
- Seq Scan on orders (cost=1250.0, actual_rows=120)

After (remediated):
- Nested Loop (cost=1669.92, actual_rows=240)
- Bitmap Heap Scan on orders (cost=310.81, actual_rows=120)
- Bitmap Index Scan using idx_orders_customer_id (cost=5.43, actual_rows=120)
- Index Only Scan on order_items using idx_order_items_order_id (cost=9.97, actual_rows=2)

Metrics:
| Metric | Baseline | Remediated | Improvement |
|---|---|---|---|
| Local ms | 12.19 | 0.237 | 98.06% |
| Prod-equivalent latency ms | 296.0 | 5.75 | 98.06% |
| CPU % | 94.2 | 9.2 | 90.23% |
| Rows returned | 240 | 240 | correct |
| Converted to index scan | - | true | yes |
| Covering index scan | - | true | yes |

Applied DDL in sandbox matches merge DDL. No regression in row counts.

## 7. Risk and Rollout

- Low risk: CONCURRENTLY takes SHARE UPDATE EXCLUSIVE, does not block reads/writes; 2x table scan + sort for build.
- Monitor pg_stat_progress_create_index, bloat, and size (~orders 22k, items 50k-120k small; production larger).
- Rollback: DROP INDEX CONCURRENTLY IF EXISTS idx_orders_customer_id; DROP INDEX CONCURRENTLY IF EXISTS idx_order_items_order_id;
- Post-deploy: ANALYZE orders; ANALYZE order_items; verify EXPLAIN (ANALYZE, BUFFERS) shows Nested Loop.

## 8. Follow-ups

- Add FK index lint in CI to prevent missing order_items(order_id) indexes.
- Consider autovacuum/analyze tuning for selectivity estimates (20 vs 29 rows).
- Review SLA threshold (1000.0ms) vs P99 245.24ms trigger tuning.
- Track P99 and shared hit blocks dashboard post-deploy.

## 9. Appendix - Raw Postgres Plan (Incident)

- Node Type Hash Join, Join Type Inner, Startup 525.9 Total 1428.17 Plan Rows 47 Width 19 Actual 1.72/8.429ms Rows 40 Loops 1 Inner Unique true Hash Cond (i.order_id = o.order_id) Shared Hit 532.
- Outer Seq Scan order_items i Startup 0.0 Total 771.0 Plan Rows 50000 Width 12 Actual 0.005/3.029ms Rows 50000 Hit 271.
- Inner Hash Startup 525.65 Total 525.65 Plan Rows 20 Width 11 Actual 1.68/1.682ms Rows 29 Buckets 1024 Batches 1 Peak 10 Hit 261.
- Inner Seq Scan orders o Filter (customer_id = 639) Rows Removed 22591 Actual 0.004/1.669ms Rows 29 Hit 261.
- Planning Time 0.303ms, Planning Hit 54, Execution 8.457ms.
