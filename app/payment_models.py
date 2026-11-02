from pydantic import BaseModel, model_validator
from typing import Any


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload with backward compatibility for v1 fields."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    @model_validator(mode='before')
    @classmethod
    def map_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Legacy 'amount' (float dollars) -> 'amount_cents' (int)
            if "amount" in data:
                if "amount_cents" not in data:
                    amt = data.pop("amount")
                    if isinstance(amt, (int, float)):
                        data["amount_cents"] = int(round(amt * 100))
                    else:
                        data["amount_cents"] = amt
                else:
                    data.pop("amount", None)
            # Legacy 'customer_address' -> 'billing.address.line1'
            if "customer_address" in data:
                if "billing" not in data:
                    addr = data.pop("customer_address")
                    data["billing"] = {"address": {"line1": addr}}
                else:
                    data.pop("customer_address", None)
            # Normalize float cents to int if caller passed float
            if "amount_cents" in data and isinstance(data["amount_cents"], float):
                data["amount_cents"] = int(round(data["amount_cents"]))
        return data

    @property
    def amount(self) -> float:
        """Backward compatibility: legacy dollars amount derived from cents."""
        return self.amount_cents / 100.0

    @property
    def customer_address(self) -> str:
        """Backward compatibility: legacy flat address derived from nested billing."""
        return self.billing.address.line1
