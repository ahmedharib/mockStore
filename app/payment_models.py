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

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        """Backward-compat: migrate legacy v1 fields to v2 schema."""
        if isinstance(data, dict):
            # amount (float dollars) -> amount_cents (int cents)
            if "amount_cents" not in data and "amount" in data:
                amt = data.pop("amount")
                data["amount_cents"] = int(round(float(amt) * 100))
            elif "amount" in data:
                data.pop("amount", None)
            # customer_address (str) -> billing.address.line1
            if "billing" not in data and "customer_address" in data:
                addr = data.pop("customer_address")
                data["billing"] = {"address": {"line1": addr}}
            elif "customer_address" in data:
                data.pop("customer_address", None)
        return data
