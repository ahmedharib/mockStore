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
            # Migrate legacy 'amount' (float dollars) -> 'amount_cents' (int)
            if "amount" in data and "amount_cents" not in data:
                amt = data.pop("amount")
                if isinstance(amt, (int, float)):
                    data["amount_cents"] = int(round(float(amt) * 100))
                else:
                    data["amount_cents"] = amt
            # Migrate legacy 'customer_address' -> 'billing.address.line1'
            if "customer_address" in data and "billing" not in data:
                addr = data.pop("customer_address")
                data["billing"] = {"address": {"line1": addr}}
            # Ensure legacy keys never leak to outbound payload
            data.pop("amount", None)
            data.pop("customer_address", None)
        return data

    # Backward-compat proxies for internal callers reading legacy attributes
    @property
    def amount(self) -> float:
        return self.amount_cents / 100.0

    @amount.setter
    def amount(self, value: float) -> None:
        object.__setattr__(self, "amount_cents", int(round(float(value) * 100)))

    @property
    def customer_address(self) -> str:
        return self.billing.address.line1

    @customer_address.setter
    def customer_address(self, value: str) -> None:
        self.billing.address.line1 = value
