from typing import Any
from pydantic import BaseModel, model_validator


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

    @model_validator(mode="before")
    @classmethod
    def map_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # Backward compatibility: map legacy 'amount' (float dollars) -> 'amount_cents' (int)
        if "amount_cents" not in data and "amount" in data:
            try:
                data["amount_cents"] = int(round(float(data["amount"]) * 100))
            except Exception:
                pass
        # Backward compatibility: map legacy 'customer_address' -> 'billing.address.line1'
        if "billing" not in data and "customer_address" in data:
            data["billing"] = {"address": {"line1": data["customer_address"]}}
        # Ensure legacy fields never appear in serialized payload
        data.pop("amount", None)
        data.pop("customer_address", None)
        return data
