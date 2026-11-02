from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload. Backward compatible with v1 legacy fields."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    @model_validator(mode="before")
    @classmethod
    def _map_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        # Legacy amount (float dollars) -> amount_cents (int cents)
        if data.get("amount_cents") is None and "amount" in data and data["amount"] is not None:
            try:
                data["amount_cents"] = int(round(float(data["amount"]) * 100))
            except Exception:
                pass
        # Legacy customer_address -> billing.address.line1
        billing = data.get("billing")
        has_line1 = (
            isinstance(billing, dict)
            and isinstance(billing.get("address"), dict)
            and isinstance(billing["address"].get("line1"), str)
            and billing["address"]["line1"].strip()
        )
        if not has_line1 and "customer_address" in data and isinstance(data["customer_address"], str) and data["customer_address"].strip():
            data["billing"] = {"address": {"line1": data["customer_address"]}}
        # Remove legacy keys so they are not persisted or serialized
        data.pop("amount", None)
        data.pop("customer_address", None)
        return data

    @field_validator("amount_cents", mode="before")
    @classmethod
    def _coerce_amount_cents(cls, v: Any) -> Any:
        if isinstance(v, float):
            return int(round(v))
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return v

    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        result = super().model_dump(**kwargs)
        result.pop("amount", None)
        result.pop("customer_address", None)
        return result
