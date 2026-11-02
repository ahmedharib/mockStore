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
        if isinstance(data, dict):
            if "amount" in data and "amount_cents" not in data:
                amt = data.pop("amount")
                data["amount_cents"] = int(round(float(amt) * 100))
            if "customer_address" in data and "billing" not in data:
                addr = data.pop("customer_address")
                data["billing"] = {"address": {"line1": addr}}
        return data

    @property
    def amount(self) -> float:
        return self.amount_cents / 100.0

    @property
    def customer_address(self) -> str:
        return self.billing.address.line1
