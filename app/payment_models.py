from pydantic import BaseModel, model_validator
from typing import Any


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload. Backward-compatible with v1 fields."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    @model_validator(mode='before')
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        # Legacy: amount (float dollars) -> amount_cents (int cents)
        if "amount_cents" not in data and "amount" in data:
            amt = data.pop("amount")
            try:
                data["amount_cents"] = int(round(float(amt) * 100))
            except Exception:
                data["amount_cents"] = amt
        # Legacy: customer_address (str) -> billing.address.line1
        if "customer_address" in data:
            addr = data.pop("customer_address")
            if "billing" not in data or not isinstance(data.get("billing"), dict):
                data["billing"] = {"address": {"line1": addr}}
            else:
                billing = data["billing"]
                if "address" not in billing or not isinstance(billing["address"], dict):
                    billing["address"] = {"line1": addr}
                elif "line1" not in billing["address"]:
                    billing["address"]["line1"] = addr
        return data

    @property
    def amount(self) -> float:
        """Backward compatibility: expose dollars as float."""
        return self.amount_cents / 100.0

    @property
    def customer_address(self) -> str:
        """Backward compatibility: expose flat address."""
        return self.billing.address.line1
