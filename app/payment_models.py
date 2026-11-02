from pydantic import BaseModel, model_validator
from typing import Any


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload sent by Cupertino Coffee Shop."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    @model_validator(mode='before')
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        """Backward compatibility: accept legacy v1 fields and migrate to v2."""
        if isinstance(data, dict):
            # Legacy 'amount' (float dollars) -> 'amount_cents' (int cents)
            if "amount" in data and "amount_cents" not in data:
                amt = data.pop("amount")
                try:
                    data["amount_cents"] = int(round(float(amt) * 100))
                except Exception:
                    data["amount_cents"] = amt
            # Legacy 'customer_address' -> 'billing.address.line1'
            if "customer_address" in data and "billing" not in data:
                addr = data.pop("customer_address")
                data["billing"] = {"address": {"line1": addr}}
            # Coerce float cents (e.g., 650.0) to int for strict v2 validation
            if "amount_cents" in data and isinstance(data["amount_cents"], float):
                data["amount_cents"] = int(round(data["amount_cents"]))
        return data
