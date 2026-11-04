from typing import Any
from pydantic import BaseModel


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload with backward-compat for v1 fields."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    def __init__(self, **data: Any):
        # Backward compatibility: legacy `amount` (dollars float) -> `amount_cents` (int)
        if data.get("amount_cents") is None and data.get("amount") is not None:
            try:
                data["amount_cents"] = int(round(float(data["amount"]) * 100))
            except (TypeError, ValueError):
                pass
        # Coerce float cents (e.g. 650.0) to int
        if isinstance(data.get("amount_cents"), float):
            data["amount_cents"] = int(round(data["amount_cents"]))
        # Never emit legacy field
        data.pop("amount", None)
        # Backward compatibility: legacy `customer_address` -> `billing.address.line1`
        if data.get("billing") is None and data.get("customer_address") is not None:
            data["billing"] = {"address": {"line1": data["customer_address"]}}
        data.pop("customer_address", None)
        super().__init__(**data)
