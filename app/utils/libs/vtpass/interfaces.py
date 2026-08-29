from decimal import Decimal
from typing import Any, Optional, Union

from pydantic import BaseModel


class VtpassOptions(BaseModel):
    api_key: str
    secret_key: str
    public_key: str
    base_url: str


class VtpassWebhookResInterface(BaseModel):
    type: Optional[str] = None
    requestId: Optional[str] = None
    transactionId: Optional[str] = None
    amount: Optional[Any] = None
    status: Optional[str] = None


class BuyAirtimeData(BaseModel):
    service_id: str
    amount: str
    phone: str


class BuyMobileDataData(BaseModel):
    service_id: str
    phone: str
    billers_code: str
    variation_code: str


class BuyElectricityData(BaseModel):
    amount: str
    service_id: str
    phone: str
    billers_code: str
    variation_code: str


class VerifyMeterNumberData(BaseModel):
    service_id: str
    billers_code: str
    type: Optional[str] = None


class BuyCableData(BaseModel):
    service_id: str
    phone: str
    billers_code: str
    variation_code: str
    amount: str
    subscription_type: str
    quantity: int = 1


class VtpassTransactions(BaseModel):
    status: str
    product_name: str
    unique_element: str
    unit_price: float
    quantity: int
    commission: float
    total_amount: float
    amount: float
    transactionId: str
    service_verification: Any = None
    channel: Optional[str] = None
    discount: Any = None
    type: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Any = None
    convinience_fee: Optional[float] = None
    platform: Optional[str] = None
    method: Optional[str] = None


class VtpassContent(BaseModel):
    transactions: VtpassTransactions


class TransactionDate(BaseModel):
    date: str
    timezone_type: int
    timezone: str


class VtpassErrorContent(BaseModel):
    errors: str | None = None


class VtpassResponse(BaseModel):
    code: str
    content: VtpassContent | VtpassErrorContent | None = None
    response_description: str | None = None
    requestId: str | None = None
    amount: Decimal | None = None
    purchased_code: str | None = None
    transaction_date: TransactionDate | str | None = None
    token: str | None = None


class VtpassVerifyMerchant(BaseModel):
    Customer_Name: str | None = None
    Account_Number: str | None = None
    Meter_Number: str | None = None
    Customer_District: str | None = None
    Business_Unit: str | None = None
    Customer_District_Reference: str | None = None
    Address: str | None = None
    Customer_Arrears: Decimal = Decimal("0")
    Minimum_Amount: Decimal | None = None
    Min_Purchase_Amount: Decimal | None = None
    Meter_Type: str | None = None
    WrongBillersCode: bool = False


class VtpassVerifyResponse(BaseModel):
    """Returned by /merchant-verify — content is customer data, not a transaction."""

    code: str
    content: VtpassVerifyMerchant | None = None


class FlattenedVtpassResponse(BaseModel):
    transaction_date: Optional[str] = None
    product_name: Optional[str] = None
    unique_element: Optional[str] = None
    commission: Optional[float] = None
    total_amount: Optional[float] = None
    amount: Optional[float] = None
    unit_price: Optional[float] = None
    quantity: Optional[int] = None
    status: Optional[str] = None
    request_id: Optional[str] = None
    request_description: Optional[str] = None
    vt_pass_transaction_id: Optional[str] = None
    token: Optional[str] = None
