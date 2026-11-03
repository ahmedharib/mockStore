from pydantic import BaseModel


class Address(BaseModel):
    """Nested street address for RoastPay v2 billing."""
    line1: str


class Billing(BaseModel):
    """Billing container required by RoastPay v2."""
    address: Address


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload sent by Cupertino Coffee Shop."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: Billing
