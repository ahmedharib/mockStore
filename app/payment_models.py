from typing import Any
from pydantic import BaseModel, ConfigDict, model_validator


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload with backward-compatible legacy migration."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Legacy 'amount' (float dollars) -> 'amount_cents' (int cents)
            if "amount_cents" not in data and "amount" in data:
                amt = data.pop("amount")
                try:
                    data["amount_cents"] = int(round(float(amt) * 100))
                except Exception:
                    data["amount_cents"] = amt
            elif "amount" in data:
                data.pop("amount", None)

            # Legacy 'customer_address' -> 'billing.address.line1'
            if "billing" not in data and "customer_address" in data:
                addr = data.pop("customer_address")
                data["billing"] = {"address": {"line1": addr}}
            elif "customer_address" in data:
                data.pop("customer_address", None)

            # Defensive coercion if amount_cents supplied as float
            if "amount_cents" in data and isinstance(data["amount_cents"], float):
                data["amount_cents"] = int(round(data["amount_cents"]))
        return data
