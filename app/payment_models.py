from pydantic import BaseModel


class BillingAddress(BaseModel):
    line1: str


class BillingInfo(BaseModel):
    address: BillingAddress


class CoffeeChargePayload(BaseModel):
    """RoastPay v2 checkout payload."""
    order_id: str
    currency: str = "USD"
    amount_cents: int
    billing: BillingInfo
