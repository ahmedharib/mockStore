from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload. Backward compatible with v1 legacy fields."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    # Legacy v1 fields - accepted for backward compatibility but excluded from serialization
    amount: Optional[float] = Field(default=None, exclude=True)
    customer_address: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Migrate amount (dollars float) -> amount_cents (int cents)
            if "amount_cents" not in data and "amount" in data and data["amount"] is not None:
                try:
                    data["amount_cents"] = int(round(float(data["amount"]) * 100))
                except Exception:
                    pass
            # Migrate customer_address (flat) -> billing.address.line1 (nested)
            if "billing" not in data and "customer_address" in data and data["customer_address"]:
                data["billing"] = {"address": {"line1": data["customer_address"]}}
        return data
