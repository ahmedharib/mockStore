# Post-Mortem: INC-20261104-PG-SEQSCAN — Hash Join Double Seq Scan on Customer Order Join

## Metadata

| Field | Value |
|---|---|
| Incident ID | INC-20261104-PG-SEQSCAN |
| Vector | VECTOR_A_DB |
| Service | postgres-live-telemetry |
| Error Code | PG_SLOW_QUERY_BREACH |
| Error Message | P99 query latency spiked to 320.84ms (SLA threshold: 1000.0ms) |
| Host CPU | null (not reported at trigger) |
| Offending Query | SELECT o.order_id, o.status, i.product_id, i.quantity FROM orders o JOIN order_items i ON o.order_id = i.order_id WHERE o.customer_id = %s |
| Severity | Slow-query breach, prod-equivalent 238.84ms |
| Status | Resolved - Ready to Merge |
| Sandbox | MODAL_CLOUD_POSTGRES_SANDBOX / sb-dpCyH11tkliMmxF9hNVSZn (4.31s) |

## Executive Summary

Autonomous SRE detected slow customer order history lookup, diagnosed double Seq Scan + Hash Join with 1775x row amplification, and verified a single covering index on order_items(order_id) that cuts latency 82.26% and CPU 75.69% with zero locks.

## Impact

- P99 breach on postgres-live-telemetry for selective customer lookup (customer_id=639 example: 27 orders, 40 rows returned).
- Production-equivalent latency 238.84ms vs local 6.824ms (35x scale factor) indicates risk under prod size/concurrency despite cache hits.
- CPU at 94.2% baseline in replay; wasted heap scans (532 hit blocks per execution + 54 planning) increase I/O/CPU per QPS.
- No data loss; correctness preserved (47 plan rows vs 40 actual, 240 rows in scaled sandbox replay).

## Timeline

- Trigger: PG_SLOW_QUERY_BREACH fired for join query.
- Diagnosis: Captured EXPLAIN (ANALYZE, BUFFERS): Hash Join Total Cost 1403.13, Execution 6.824ms, Planning 0.162ms.
- Analysis: Identified missing indexes on orders(customer_id) and order_items(order_id); determined order_items 50k scan is dominant; prior orders-only index attempt failed with 18.63% gain.
- Fix Candidate: Covering btree on order_items(order_id) INCLUDE (product_id, quantity) with CONCURRENTLY + timeouts.
- Verification: Applied in sandbox sb-dpCyH11tkliMmxF9hNVSZn, 4.31s, before/after EXPLAIN compared, deterministic gate passed.
- Merge: This PR proposes production rollout.

## Root Cause Analysis

Plan tree:
- Hash Join (cost 1403.13, startup 500.85, plan rows 47, actual 40, Hash Cond i.order_id=o.order_id, Inner Unique true)
  - Outer: Seq Scan on order_items i (cost 771.0, plan 50000, actual 50000, 271 hit blocks)
  - Inner Hash (cost 500.62, plan 18, actual 27, buckets 1024, batches 1, peak 10kB)
    - Seq Scan on orders o (cost 500.62, plan 18, actual 27, filter customer_id=639, rows removed 21078, 261 hit blocks)

Details:
- No supporting btree for highly selective equality predicate on orders.customer_id (only orders_pkey on order_id). Filter removes 99.87% in heap.
- No FK/join index on order_items(order_id) forces full 50k probe of hash.
- Rows scanned ~71000 (50000+21078+27) vs 40 returned = ~1775x amplification; 1250x on large table alone.
- Cost split: 771.0 order_items + 500.62 orders + hash overhead. Startup dominated by hash build (0.897ms of 6.812ms total).
- Buffers: 532 hit, 0 read/dirty/write, 0 temp/local; fully cached yet slow due to CPU + heap tuple visits.
- Stats skew: Plan Rows 18 vs Actual 27 suggests stale stats, but index fixes access path regardless.

Why orders-only index insufficient: Leaves outer 50k scan untouched; hash join remains. Fix must eliminate large-table scan first.

## Resolution - Verified DDL / Diff

Production-safe migration (CONCURRENTLY, IF NOT EXISTS, timeouts to avoid lock pileup):

```sql
SET statement_timeout = '30s';
SET lock_timeout = '5s';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_order_items_order_id ON public.order_items USING btree (order_id) INCLUDE (product_id, quantity);
```

Design notes:
- btree on join key order_id for Nested Loop probe.
- INCLUDE (product_id, quantity) makes it covering for SELECT list -> Index Only Scan, no heap fetch.
- CONCURRENTLY avoids ACCESS EXCLUSIVE blocking writes; safe for live telemetry table.
- Single index minimizes write amplification vs dual-index approach. Follow-up: evaluate orders(customer_id) index if selective filter Seq Scan (120 rows in scaled test) becomes bottleneck; currently Nested Loop outer Seq Scan on orders is acceptable (120 rows, cost 1250.0) given small filtered set.
- Recommend ANALYZE public.order_items after build to refresh planner stats.

## Sandbox Verification Proof

Environment: MODAL_CLOUD_POSTGRES_SANDBOX, ID sb-dpCyH11tkliMmxF9hNVSZn, duration 4.31s, applied DDL identical to PR.

Before:
- Hash Join (cost 3531.5, actual 240)
- Seq Scan on order_items (cost 1965.0, actual 120000)
- Hash (cost 1250.0, actual 120)
- Seq Scan on orders (cost 1250.0, actual 120)
- Baseline local 12.759ms, baseline prod-equivalent 238.84ms, CPU 94.2%

After:
- Nested Loop (cost 2449.09, actual 240)
- Seq Scan on orders (cost 1250.0, actual 120) [small outer, retained]
- Index Only Scan on order_items using idx_order_items_order_id (cost 10.14, actual 2 per loop) [covering]
- Remediated local 2.264ms, remediated prod-equivalent 42.38ms, CPU 22.9%

| Metric | Before | After | Delta |
|---|---|---|---|
| Local ms | 12.759 | 2.264 | -82.25% |
| Prod-equivalent ms | 238.84 | 42.38 | -82.26% |
| CPU % | 94.2 | 22.9 | -75.69% |
| Plan | Hash Join + double Seq Scan | Nested Loop + Index Only Scan | converted_to_index_scan=true, is_covering=true |
| Rows returned | 240 | 240 | correct |
| Table locks | - | false | safe |
| Deterministic gate | - | passed | true |

Raw production plan reference: Total Cost 1403.13, Execution 6.824ms, Planning 0.162ms, Shared Hit 532, Hash Buckets 1024, Peak 10kB, Filter removes 21078.

Conclusion: Dominant 50k heap scan eliminated; probe cost drops from 771.0 to ~10.14 per outer batch; 82%+ latency win exceeds threshold for merge.

## Lessons Learned

- Selective equality + join without indexes defaults to Hash Join + Seq Scans with massive amplification even when cached.
- Large-table (outer) scan dominates; always index join/FK column first.
- Covering INCLUDE avoids heap visits and unlocks Index Only Scan.
- CONCURRENTLY + IF NOT EXISTS + timeouts required for zero-downtime DDL on hot tables.
- Local vs prod-equivalent 35x gap highlights need for scale-aware replay.

## Action Items

| Action | Owner | Priority |
|---|---|---|
| Merge this index CONCURRENTLY during low-traffic window, then ANALYZE order_items | DBA / SRE | P0 |
| Monitor P99, plan cache, index bloat, write overhead on order_items | SRE | P1 |
| Evaluate follow-up index on orders(customer_id) INCLUDE (order_id, status) if outer Seq Scan regresses | Backend | P2 |
| Add FK index lint in CI to prevent missing join indexes | Platform | P2 |
| Update stats/autovacuum thresholds for orders/order_items | DBA | P3 |

## Appendix

- Incident trigger JSON preserved in ticket INC-20261104-PG-SEQSCAN.
- Raw Postgres JSON plan: Hash Join -> Seq Scan order_items (50000) + Hash -> Seq Scan orders (27, filter removes 21078).
- Verified patch hash matches sandbox applied_ddl; error=null.
