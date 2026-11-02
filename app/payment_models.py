from pydantic import BaseModel, ConfigDict, model_validator
from typing import Any


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload.

    Upstream v2 requires integer `amount_cents` and nested `billing.address.line1`.
    Legacy fields `amount` (float dollars) and `customer_address` (flat string)
    are migrated via a pre-validator to preserve backward compatibility for
    internal callers.
    """

    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Migrate legacy `amount` (dollars as float) -> `amount_cents` (int)
            if "amount_cents" not in data and "amount" in data:
                amt = data.pop("amount")
                if amt is not None:
                    try:
                        data["amount_cents"] = int(round(float(amt) * 100))
                    except Exception:
                        pass
            # Migrate legacy `customer_address` -> `billing.address.line1`
            if "billing" not in data and "customer_address" in data:
                addr = data.pop("customer_address")
                if addr is not None:
                    data["billing"] = {"address": {"line1": str(addr)}}
            # Remove any residual legacy keys so they never appear in model_dump()
            data.pop("amount", None)
            data.pop("customer_address", None)
        return data
