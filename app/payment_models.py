from pydantic import BaseModel, ConfigDict, model_validator
from typing import Any


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload sent by Cupertino Coffee Shop.

    v2 contract requires:
    - amount_cents: int (converted from dollars)
    - billing.address.line1: str (nested from customer_address)

    Backward compatibility: legacy fields `amount` and `customer_address`
    are accepted via pre-validation and mapped to v2 fields, and exposed
    as read-only properties.
    """
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode='before')
    @classmethod
    def map_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # Map legacy amount (float dollars) -> amount_cents (int)
        if "amount_cents" not in data and "amount" in data:
            amt = data.pop("amount")
            try:
                data["amount_cents"] = int(round(float(amt) * 100))
            except Exception:
                data["amount_cents"] = amt
        # Map legacy customer_address -> billing.address.line1
        if "billing" not in data and "customer_address" in data:
            addr = data.pop("customer_address")
            data["billing"] = {"address": {"line1": addr}}
        # Ensure legacy keys never leak to v2 payload
        data.pop("amount", None)
        data.pop("customer_address", None)
        return data

    @property
    def amount(self) -> float:
        """Backward compat: dollars as float."""
        return self.amount_cents / 100.0

    @property
    def customer_address(self) -> str:
        """Backward compat: flat address string."""
        return self.billing.address.line1
