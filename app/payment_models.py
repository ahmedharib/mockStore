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
        """Backward compatibility: accept legacy v1 fields and coerce to v2."""
        if isinstance(data, dict):
            # amount (float dollars) -> amount_cents (int)
            if "amount" in data and "amount_cents" not in data:
                amt = data.pop("amount")
                if amt is not None:
                    data["amount_cents"] = int(round(float(amt) * 100))
            # total_dollars alias -> amount_cents
            if "total_dollars" in data and "amount_cents" not in data:
                td = data.pop("total_dollars")
                data["amount_cents"] = int(round(float(td) * 100))
            # customer_address (flat) -> billing.address.line1 (nested)
            if "customer_address" in data and "billing" not in data:
                addr = data.pop("customer_address")
                data["billing"] = {"address": {"line1": addr}}
            if "street_address" in data and "billing" not in data:
                sa = data.pop("street_address")
                data["billing"] = {"address": {"line1": sa}}
        return data

    @model_validator(mode='after')
    def _coerce_cents_int(self) -> "CoffeeChargePayload":
        if isinstance(self.amount_cents, float):
            object.__setattr__(self, "amount_cents", int(round(self.amount_cents)))
        return self

    # Backward-compatible read access for internal callers still using legacy names
    @property
    def amount(self) -> float:
        return self.amount_cents / 100.0

    @property
    def customer_address(self) -> str:
        return self.billing.address.line1
