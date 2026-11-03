from typing import Optional
from pydantic import BaseModel, Field, model_validator


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload with backward-compat for v1 fields."""
    order_id: str
    currency: str = "USD"
    amount_cents: Optional[int] = None
    billing: Optional[Billing] = None
    # Legacy v1 fields (deprecated, never sent upstream)
    amount: Optional[float] = Field(default=None, exclude=True)
    customer_address: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _coerce_legacy(self):
        # Legacy amount (dollars float) -> amount_cents (int)
        if self.amount_cents is None and self.amount is not None:
            object.__setattr__(self, "amount_cents", int(round(self.amount * 100)))
        # Coerce float cents to int if passed as float
        if isinstance(self.amount_cents, float):
            object.__setattr__(self, "amount_cents", int(round(self.amount_cents)))
        # Legacy customer_address -> billing.address.line1
        if self.billing is None and self.customer_address is not None:
            object.__setattr__(self, "billing", Billing(address=Address(line1=self.customer_address)))
        # Allow dict input that may have slipped through (defensive)
        if isinstance(self.billing, dict):
            addr = self.billing.get("address", {})
            if isinstance(addr, dict) and "line1" in addr:
                object.__setattr__(self, "billing", Billing(address=Address(line1=addr["line1"])))
            elif isinstance(addr, str):
                object.__setattr__(self, "billing", Billing(address=Address(line1=addr)))
        if self.amount_cents is None:
            raise ValueError("Missing required field 'amount_cents' (or legacy 'amount').")
        if not isinstance(self.amount_cents, int) or isinstance(self.amount_cents, bool):
            raise ValueError("Field 'amount_cents' must be integer.")
        if self.billing is None or not isinstance(self.billing.address.line1, str) or not self.billing.address.line1.strip():
            raise ValueError("Missing required nested field 'billing.address.line1' (or legacy 'customer_address').")
        return self
