import random
import string
import time
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status

from .interfaces import (
    PaystackInitializeTransaction,
    PaystackMetadata,
    PaystackOptions,
    PaystackVerifyTransactions,
    RedirectToPaymentBody,
)

_TIMEOUT = 30.0
_DEFAULT_CALLBACK_URL = "https://hethera.ai/payment-callback"


class PaystackService:
    def __init__(self, options: PaystackOptions) -> None:
        self._options = options
        self._client = self._build_client()

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._options.base_url,
            timeout=_TIMEOUT,
            headers={
                "Authorization": f"Bearer {self._options.secret_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    async def _request(self, method: str, url: str, data: dict | None = None) -> dict:
        try:
            if method.upper() == "GET":
                response = await self._client.get(url)

            else:
                response = await self._client.post(url, json=data or {})

            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Request timed out"
            )
        except httpx.HTTPStatusError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payment service down, try again later",
            )
        except httpx.HTTPError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payment service down, try again later",
            )

    async def add_transfer_recipient(
        self,
        account_name: str,
        account_number: str,
        bank_code: str,
    ) -> str:
        body = {
            "type": "nuban",
            "name": account_name,
            "description": f"Account Description for {account_name}",
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN",
        }
        response = await self._request("POST", "/transferrecipient", body)

        if response and response.get("status"):
            return response.get("data", {}).get("recipient_code", "")

        return ""

    async def redirect_to_payment(self, body: RedirectToPaymentBody) -> dict | None:
        payload = body.model_dump(exclude_none=True)
        payload["reference"] = self.generate_reference()
        payload["callback_url"] = payload.get("callback_url") or _DEFAULT_CALLBACK_URL
        payload["amount"] = self._to_kobo(body.amount)
        payload["order_id"] = payload.get("order_id") or self.generate_reference()
        payload.setdefault("channel", "")

        if payload.get("metadata") is None:
            payload["metadata"] = {}

        response = await self._request("POST", "/transaction/initialize", payload)

        if response and response.get("data", {}).get("authorization_url"):
            return response

        return None

    async def charge_customer(
        self,
        amount: float,
        card_authorization_code: str,
        user_email: str,
        metadata: Optional[PaystackMetadata] = None,
    ) -> dict:
        body: dict[str, Any] = {
            "amount": self._to_kobo(amount),
            "authorization_code": card_authorization_code,
            "email": user_email,
            "reference": self.generate_reference(),
        }

        if metadata:
            body["metadata"] = metadata.model_dump(exclude_none=True)

        return await self._request("POST", "/transaction/charge_authorization", body)

    async def initiate_transfer(
        self,
        payment_id: str,
        amount: float,
        reason: str = "Personal Payment",
    ) -> dict:
        body = {
            "source": "balance",
            "amount": self._to_kobo(amount),
            "recipient": payment_id,
            "reason": reason,
            "reference": self.generate_reference(),
        }

        return await self._request("POST", "/transfer", body)

    async def verify_payment(self, ref: str) -> dict:
        return await self._request("GET", f"/transaction/verify/{ref}")

    async def refund_transaction(
        self, transaction_reference: str, amount: float | None = None
    ) -> dict:
        """Initiate a Paystack refund for a previously charged reference."""
        body: dict = {"transaction": transaction_reference}

        if amount is not None:
            body["amount"] = self._to_kobo(amount)

        return await self._request("POST", "/refund", body)

    async def verify_transfer(self, ref: str) -> dict:
        return await self._request("GET", f"/transfer/verify/{ref}")

    async def resolve_account_number(self, account_number: str, bank_code: str) -> dict:
        return await self._request(
            "GET",
            f"/bank/resolve?account_number={account_number}&bank_code={bank_code}",
        )

    async def resolve_bvn(self, bvn: str) -> dict:
        return await self._request("GET", f"/identity/bvn/resolve/{bvn}")

    async def list_banks(self) -> dict:
        return await self._request("GET", "/bank")

    async def list_transactions(self) -> dict:
        return await self._request("GET", "/transaction")

    async def get_balance(self) -> dict:
        return await self._request("GET", "/balance")

    # --- fee calculators ---

    def transaction_charge(self, amount: float) -> float:
        ratio = 0.015
        settled = amount * ratio if amount < 2500 else amount * ratio + 100
        return min(settled, 2000)

    def calculate_settlement(self, amount: float) -> float:
        ratio = 0.015
        settled = amount * ratio if amount < 2500 else amount * ratio + 100
        return min(settled, 2000)

    def transfer_charge(self, amount: float) -> int:
        if amount < 5000:
            return 10

        if amount > 50000:
            return 50

        return 25

    # --- helpers ---

    def generate_reference(self) -> str:
        prefix = "".join(random.choices(string.ascii_letters, k=2))
        return f"{prefix}{hex(int(time.time() * 1000))[2:]}"

    @staticmethod
    def _to_kobo(amount: float) -> int:
        return int(amount * 100)

    async def aclose(self) -> None:
        await self._client.aclose()
