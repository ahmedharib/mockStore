from typing import Any
from pydantic import BaseModel, model_validator


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

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: Any) -> Any:
        """Backward-compat: migrate v1 `amount`/`customer_address` to v2."""
        if isinstance(data, dict):
            migrated = dict(data)
            if "amount_cents" not in migrated and "amount" in migrated:
                try:
                    migrated["amount_cents"] = int(round(float(migrated.pop("amount")) * 100))
                except (TypeError, ValueError):
                    pass
            elif "amount" in migrated:
                migrated.pop("amount", None)
            if "billing" not in migrated and "customer_address" in migrated:
                migrated["billing"] = {"address": {"line1": migrated.pop("customer_address")}}
            elif "customer_address" in migrated:
                migrated.pop("customer_address", None)
            return migrated
        return data
