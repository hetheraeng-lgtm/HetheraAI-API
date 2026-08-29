from typing import Any, Optional

from pydantic import BaseModel


class PaystackOptions(BaseModel):
    base_url: str
    secret_key: str
    merchant_email: Optional[str] = None
    public_key: Optional[str] = None


class PaystackMetadata(BaseModel):
    webhook_condition: Optional[str] = None
    extra_data: Any = None


class RedirectToPaymentBody(BaseModel):
    amount: float
    email: str
    reference: Optional[str] = None
    callback_url: Optional[str] = None
    metadata: Optional[PaystackMetadata] = None
    order_id: Optional[str] = None
    channel: Optional[str] = None


class PaystackTransactionData(BaseModel):
    authorization_url: str
    access_code: str
    reference: str


class PaystackInitializeTransaction(BaseModel):
    status: bool
    message: str
    data: PaystackTransactionData


class PaystackCustomer(BaseModel):
    id: Any = None
    first_name: Any = None
    last_name: Any = None
    email: Any = None
    customer_code: Any = None
    phone: Any = None
    metadata: Any = None
    risk_action: Any = None
    international_format_phone: Any = None


class PaystackVerifyTransactionData(BaseModel):
    id: Any = None
    domain: Optional[str] = None
    status: Optional[str] = None
    reference: Optional[str] = None
    amount: Any = None
    message: Any = None
    gateway_response: Any = None
    paid_at: Any = None
    created_at: Any = None
    channel: Any = None
    currency: Any = None
    ip_address: Any = None
    metadata: Any = None
    fees: Any = None
    authorization: Any = None
    customer: Optional[PaystackCustomer] = None
    plan: Any = None
    order_id: Any = None
    requested_amount: Any = None
    transaction_date: Any = None
    subaccount: Any = None


class PaystackVerifyTransactions(BaseModel):
    status: Any
    message: Any
    data: PaystackVerifyTransactionData
