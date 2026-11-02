from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, model_validator


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload sent by Cupertino Coffee Shop.

    v2 contract requires integer amount_cents and nested billing.address.line1.
    Legacy fields amount/customer_address are handled via validator for backward compatibility
    and are never serialized.
    """
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _handle_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, Dict):
            # Legacy: amount (float dollars) -> amount_cents (int cents)
            if "amount_cents" not in data and "amount" in data:
                try:
                    data["amount_cents"] = int(round(float(data.pop("amount")) * 100))
                except Exception:
                    data.pop("amount", None)
            else:
                data.pop("amount", None)

            # Legacy: customer_address -> billing.address.line1
            if "customer_address" in data:
                legacy_addr = data.pop("customer_address")
                if "billing" not in data or not isinstance(data.get("billing"), dict):
                    data["billing"] = {"address": {"line1": legacy_addr}}
                else:
                    billing = data["billing"]
                    if "address" not in billing or not isinstance(billing["address"], dict):
                        billing["address"] = {"line1": legacy_addr}
                    elif "line1" not in billing["address"]:
                        billing["address"]["line1"] = legacy_addr
        return data

    @property
    def amount(self) -> float:
        """Backward-compatible accessor: dollars as float."""
        return self.amount_cents / 100.0

    @property
    def customer_address(self) -> str:
        """Backward-compatible accessor: street address."""
        return self.billing.address.line1
