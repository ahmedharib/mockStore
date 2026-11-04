# Post-Mortem — INC-20261104-API-5ED5D1: RoastPay v2 Schema Drift (422 on /api/v1/orders/checkout)

## Metadata

| Field | Value |
|---|---|
| Incident ID | INC-20261104-API-5ED5D1 |
| Vector | VECTOR_B_API_CONTRACT |
| Service | cupertino-coffee-store |
| Endpoint | POST /api/v1/orders/checkout |
| Upstream | POST /v1/coffee/charges (RoastPay v2) |
| HTTP Status | 422 Unprocessable Entity |
| Error Code | ROASTPAY_V2_SCHEMA_DRIFT |
| Severity | P1 - Checkout blocked |
| Detection | pytest `tests/test_payment_checkout.py::test_coffee_order_checkout_conforms_to_roastpay_v2` + live traceback |

## Executive Summary

Checkout for Cupertino Coffee Store failed with HTTP 422 after RoastPay enforced v2 contract. Legacy v1 payload using float `amount` and flat `customer_address` was rejected. Autonomous SRE diagnosed 4 breaking changes, migrated models and builder to `amount_cents: int` and `billing.address.line1: str`, and verified with passing sandbox test. No DB migration required.

## Impact

- 100% of `POST /api/v1/orders/checkout` calls raising `UpstreamContractError: HTTP 422`.
- Example order `ORD-LATTE-1042` ($6.50) blocked.
- Customer-facing checkout unusable until v2 conformance.

## Timeline (UTC 2026-11-04)

- **Trigger:** `charge_coffee_order` -> `_simulate_roastpay_v2_gateway(payload)` raises `ROASTPAY_V2_SCHEMA_DRIFT` with messages: Field 'amount' (float) was removed in v2; send integer 'amount_cents' / Field 'customer_address' was removed; send 'billing.address.line1' / Missing `amount_cents` / Missing `billing.address.line1`.
- **Test failure:** `assert 'amount' not in {'order_id':'ORD-LATTE-1042','currency':'USD','amount':6.5,'customer_address':'1 Infinite Loop, Cupertino, CA 95014'}` FAILED.
- **Diagnosis:** Confirmed BREAKING drift: FIELD_REMOVED + 2x FIELD_NEWLY_REQUIRED + FIELD_STRUCTURALLY_NESTED.
- **Fix applied:** Updated `app/payment_models.py` + `app/payment_client.py`.
- **Verification:** MODAL_CLOUD_CONTAINER `sb-2p8NZVNJpPWrecL8hlcHFH` PASSED in 4.36s.

## Root Cause Analysis

See `root_cause_analysis` field. Upstream v2 removed float dollars in favor of integer cents to avoid floating-point rounding, and normalized address into `billing.address` object for future expansion (line2, city, zip). Downstream was not version-pinned or contract-tested, so drift reached production checkout path. Pydantic v1 model allowed invalid payload to be built without upstream validation until gateway rejection.

## Resolution — Verified Diff

Applied files: `app/payment_models.py`, `app/payment_client.py`

```diff
--- a/app/payment_models.py
+++ b/app/payment_models.py
@@ -1,9 +1,17 @@
 from pydantic import BaseModel
 
 
+class Address(BaseModel):
+    line1: str
+
+
+class Billing(BaseModel):
+    address: Address
+
+
 class CoffeeChargePayload(BaseModel):
-    """Legacy v1 checkout payload sent by Cupertino Coffee Shop."""
+    """RoastPay v2 checkout payload."""
     order_id: str
     currency: str = "USD"
-    amount: float
-    customer_address: str
+    amount_cents: int
+    billing: Billing

--- a/app/payment_client.py
+++ b/app/payment_client.py
@@ -39,12 +39,13 @@
 
 
 def build_charge_payload(order_id: str, total_dollars: float, street_address: str) -> Dict[str, Any]:
-    """Builds the outbound JSON dictionary for RoastPay."""
+    """Builds the outbound JSON dictionary for RoastPay v2."""
+    amount_cents = int(round(total_dollars * 100))
     model = CoffeeChargePayload(
         order_id=order_id,
         currency="USD",
-        amount=total_dollars,
-        customer_address=street_address,
+        amount_cents=amount_cents,
+        billing={"address": {"line1": street_address}},
     )
     return model.model_dump()
```

Key logic: `amount_cents = int(round(total_dollars * 100))` ensures 6.5 -> 650, 6.55 -> 655 without float drift. Nested `billing={"address": {"line1": street_address}}` satisfies required leaf `billing.address.line1` and is validated by Pydantic `Billing/Address` models.

## Sandbox Verification Proof

- Runner: MODAL_CLOUD_CONTAINER
- Sandbox ID: sb-2p8NZVNJpPWrecL8hlcHFH
- Passed: true, Exit Code: 0, Duration: 4.36s
- Test Target: tests/test_payment_checkout.py
- Dependencies: pytest, pydantic, httpx, fastapi>=0.110.0, uvicorn[standard]>=0.29.0, psycopg2-binary>=2.9.9, locust>=2.24.0
- Applied Files: app/payment_models.py, app/payment_client.py

```
============================= test session starts ==============================
platform linux -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0 -- /usr/local/bin/python
cachedir: .pytest_cache
rootdir: /tmp/repo
plugins: anyio-4.16.0, locust-2.47.0
collecting ... collected 1 item
tests/test_payment_checkout.py::test_coffee_order_checkout_conforms_to_roastpay_v2 PASSED [100%]
============================== 1 passed in 0.11s ===============================
```

stderr: (empty)

## Lessons Learned

- Upstream payment contracts need version pinning and consumer-driven contract tests in CI.
- Float money fields are fragile; integer cents should have been adopted earlier.
- Flat address fields do not survive gateway normalization; nested billing model is more extensible.

## Action Items

- [ ] Add Pact/contract test for RoastPay v2 schema to block v1 payloads pre-merge.
- [ ] Add unit test for dollars-to-cents edge cases (e.g., 0.015, 19.99).
- [ ] Monitor /api/v1/orders/checkout 422 rate and alert on ROASTPAY_V2_SCHEMA_DRIFT.
- [ ] Document RoastPay v2 migration in API changelog and pin gateway version.

## References

- Incident: INC-20261104-API-5ED5D1
- Failing payload: {'order_id':'ORD-LATTE-1042','currency':'USD','amount':6.5,'customer_address':'1 Infinite Loop, Cupertino, CA 95014'}
- Expected v2 payload shape: {'order_id':'ORD-LATTE-1042','currency':'USD','amount_cents':650,'billing':{'address':{'line1':'1 Infinite Loop, Cupertino, CA 95014'}}}
