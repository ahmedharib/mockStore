from typing import Any, Dict
from pydantic import BaseModel, model_validator


class Address(BaseModel):
    """Nested address object for RoastPay v2."""
    line1: str


class Billing(BaseModel):
    """Billing container for RoastPay v2."""
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload sent by Cupertino Coffee Shop."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_v1(cls, data: Any) -> Any:
        """Backward-compat: migrate legacy v1 fields to v2 shape."""
        if isinstance(data, dict):
            d: Dict[str, Any] = dict(data)
            # amount (dollars float) -> amount_cents (int)
            if "amount_cents" not in d and "amount" in d:
                try:
                    d["amount_cents"] = int(round(float(d.pop("amount")) * 100))
                except Exception:
                    pass
            elif "amount" in d:
                d.pop("amount", None)
            # customer_address (flat str) -> billing.address.line1
            if "billing" not in d and "customer_address" in d:
                d["billing"] = {"address": {"line1": d.pop("customer_address")}}
            elif "customer_address" in d:
                d.pop("customer_address", None)
            return d
        return data
