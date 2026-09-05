import logging
import random
import re
import string
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException, status

from .enums import VTPASS_ERRORS, VTPASS_SUCCESS
from .interfaces import (
    BuyAirtimeData,
    BuyCableData,
    BuyElectricityData,
    BuyMobileDataData,
    FlattenedVtpassResponse,
    VtpassContent,
    VtpassOptions,
    VtpassResponse,
    VerifyMeterNumberData,
    VtpassVerifyResponse,
)

_TIMEOUT = 120.0


class VtpassService:
    def __init__(self, options: VtpassOptions) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._options = options
        self._client = self._build_client()

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._options.base_url,
            timeout=_TIMEOUT,
            headers={
                "api-key": self._options.api_key,
                "secret-key": self._options.secret_key,
                "public-key": self._options.public_key,
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
            self._logger.error("VTPass request timed out: %s %s", method, url)

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Request timed out"
            )
        except httpx.HTTPStatusError as exc:
            self._logger.error(
                "VTPass HTTP error %s %s: %s", method, url, exc.response.text
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal Server Error",
            )
        except httpx.HTTPError as exc:
            self._logger.error("VTPass request error %s %s: %s", method, url, exc)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal Server Error",
            )

    async def buy_airtime(
        self, data: BuyAirtimeData
    ) -> tuple[FlattenedVtpassResponse | None, str | None]:
        try:
            request_id = self._generate_request_id()
            payload = {
                "serviceID": data.service_id,
                "phone": data.phone,
                "amount": data.amount,
                "request_id": request_id,
            }

            raw = await self._request("POST", "/pay", payload)

            response = VtpassResponse(**raw)
            self._handle_vtpass_error(response, "Airtime purchase failed")

            return self._flatten_response(response), None
        except Exception as exc:
            self._logger.error("Airtime purchase failed: %s", exc)

            return (
                None,
                getattr(exc, "detail", str(exc))
                or "Unable to source this network airtime at the moment",
            )

    async def verify_purchase(
        self, request_id: str
    ) -> tuple[VtpassResponse | None, str | None]:
        try:
            raw = await self._request("POST", "/requery", {"request_id": request_id})

            response = VtpassResponse(**raw)
            self._handle_vtpass_error(response, "Purchase verification failed")

            return response, None
        except Exception as exc:
            self._logger.error("Purchase verification failed: %s", exc)

            return (
                None,
                getattr(exc, "detail", str(exc))
                or "Unable to verify purchase at the moment",
            )

    async def buy_mobile_data(
        self, data: BuyMobileDataData
    ) -> tuple[FlattenedVtpassResponse | None, str | None]:
        try:
            request_id = self._generate_request_id()
            payload = {
                "serviceID": data.service_id,
                "phone": data.phone,
                "billersCode": data.billers_code,
                "variation_code": data.variation_code,
                "quantity": 1,
                "request_id": request_id,
            }

            raw = await self._request("POST", "/pay", payload)
            response = VtpassResponse(**raw)

            self._handle_vtpass_error(response, "Mobile data purchase failed")

            return self._flatten_response(response), None
        except Exception as exc:
            self._logger.error("Mobile data purchase failed: %s", exc)

            return (
                None,
                getattr(exc, "detail", str(exc))
                or "Unable to source this network data at the moment",
            )

    async def get_variation_codes(self, service_id: str) -> dict:
        raw = await self._request("GET", f"/service-variations?serviceID={service_id}")
        response_code = raw.get("code", "")

        if response_code in VTPASS_ERRORS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=VTPASS_ERRORS[response_code],
            )

        return raw.get("content", {})

    async def get_balance(self) -> tuple[dict | None, str | None]:
        try:
            raw = await self._request("GET", "/balance")
            response_code = raw.get("code", "")

            if response_code in VTPASS_ERRORS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=VTPASS_ERRORS[response_code],
                )

            return raw, None
        except Exception as exc:
            self._logger.error("Failed to retrieve VTPass balance: %s", exc)

            return (
                None,
                getattr(exc, "detail", str(exc))
                or "Unable to get VTPass balance at the moment",
            )

    async def verify_merchant(
        self, data: VerifyMeterNumberData
    ) -> tuple[VtpassVerifyResponse | None, str | None]:
        try:
            request_id = self._generate_request_id()
            payload = {
                "serviceID": data.service_id,
                "billersCode": data.billers_code,
                "request_id": request_id,
            }

            if data.type:
                payload["type"] = data.type

            raw = await self._request("POST", "/merchant-verify", payload)
            response = VtpassVerifyResponse(**raw)

            if response.code not in ("000", "099"):
                raise Exception(f"Merchant verification failed: code={response.code}")

            return response, None
        except Exception as exc:
            self._logger.error("Merchant verification failed: %s", exc)
            return (
                None,
                getattr(exc, "detail", str(exc))
                or "Unable to complete merchant verification at the moment",
            )

    async def buy_electricity(
        self, data: BuyElectricityData
    ) -> tuple[FlattenedVtpassResponse | None, str | None]:
        try:
            request_id = self._generate_request_id()
            payload = {
                "serviceID": data.service_id,
                "phone": data.phone,
                "amount": data.amount,
                "billersCode": data.billers_code,
                "variation_code": data.variation_code,
                "quantity": 1,
                "request_id": request_id,
            }

            raw = await self._request("POST", "/pay", payload)
            response = VtpassResponse(**raw)

            self._handle_vtpass_error(response, "Electricity purchase failed")

            return self._flatten_response(response), None
        except Exception as exc:
            self._logger.error("Electricity purchase failed: %s", exc)

            return (
                None,
                getattr(exc, "detail", str(exc))
                or "Unable to complete electric bills payment at the moment",
            )

    async def buy_cable(
        self, data: BuyCableData
    ) -> tuple[FlattenedVtpassResponse | None, str | None]:
        try:
            request_id = self._generate_request_id()
            payload = {
                "serviceID": data.service_id,
                "phone": data.phone,
                "billersCode": data.billers_code,
                "variation_code": data.variation_code,
                "amount": data.amount,
                "subscription_type": data.subscription_type,
                "quantity": data.quantity,
                "request_id": request_id,
            }

            raw = await self._request("POST", "/pay", payload)
            response = VtpassResponse(**raw)

            self._handle_vtpass_error(response, "Cable purchase failed")

            return self._flatten_response(response), None
        except Exception as exc:
            self._logger.error("Cable purchase failed: %s", exc)

            return (
                None,
                getattr(exc, "detail", str(exc))
                or "Unable to complete cable bills payment at the moment",
            )

    # --- helpers ---

    def _flatten_response(self, res: VtpassResponse) -> FlattenedVtpassResponse:
        if not isinstance(res.content, VtpassContent):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unexpected VTPass response format",
            )

        tx = res.content.transactions
        td = res.transaction_date
        transaction_date = getattr(td, "date", None) or str(td)

        token: Optional[str] = None

        if res.purchased_code:
            parts = re.split(r"[Tt]oken\s*:\s{1,2}", res.purchased_code)
            token = parts[1] if len(parts) > 1 else None

        return FlattenedVtpassResponse(
            product_name=tx.product_name,
            unique_element=tx.unique_element,
            commission=tx.commission,
            total_amount=tx.total_amount,
            amount=float(res.amount) if res.amount is not None else None,
            unit_price=tx.unit_price,
            quantity=tx.quantity,
            status=tx.status,
            request_id=res.requestId,
            request_description=res.response_description,
            vt_pass_transaction_id=tx.transactionId,
            token=token,
            transaction_date=transaction_date,
        )

    def _generate_request_id(self) -> str:
        lagos_now = datetime.now(ZoneInfo("Africa/Lagos"))
        timestamp = lagos_now.strftime("%Y%m%d%H%M")
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"{timestamp}{suffix}"

    def _handle_vtpass_error(self, response: VtpassResponse, msg_prefix: str) -> None:
        if response.code not in VTPASS_ERRORS:
            return

        err_msg = VTPASS_ERRORS[response.code]

        if err_msg == "Low wallet balance":
            err_msg = "Unable to make a purchase at this time"

        self._logger.warning("%s: %s", msg_prefix, err_msg)

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
