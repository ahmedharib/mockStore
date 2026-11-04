from pydantic import BaseModel


class Address(BaseModel):
    line1: str


class Billing(BaseModel):
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing
