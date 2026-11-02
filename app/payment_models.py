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
        """Backward-compatibility: translate legacy v1 fields to v2."""
        if isinstance(data, dict):
            # amount (float dollars) -> amount_cents (int)
            if "amount" in data and "amount_cents" not in data:
                amt = data.pop("amount")
                try:
                    data["amount_cents"] = int(round(float(amt) * 100))
                except Exception:
                    data["amount_cents"] = amt
            # customer_address (flat string) -> billing.address.line1
            if "customer_address" in data and "billing" not in data:
                addr = data.pop("customer_address")
                data["billing"] = {"address": {"line1": addr}}
        return data

    # Backward-compatibility accessors for internal callers reading legacy attributes
    @property
    def amount(self) -> float:
        return self.amount_cents / 100.0

    @property
    def customer_address(self) -> str:
        return self.billing.address.line1
