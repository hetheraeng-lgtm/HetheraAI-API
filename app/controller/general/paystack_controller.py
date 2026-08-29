import hashlib
import hmac
import json
import logging

_log = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import app_settings
from app.config.database import get_db

from app.service.card_service import CardService
from app.utils.libs.paystack.interfaces import PaystackOptions
from app.utils.libs.paystack.service import PaystackService
from app.utils.swagger.paystack import WEBHOOK_OPENAPI_EXTRA, _EXAMPLE_SIGNATURE

router = APIRouter(prefix="/paystack", tags=["Paystack"])


def _get_paystack() -> PaystackService:
    return PaystackService(
        PaystackOptions(
            base_url=app_settings.PAYSTACK_BASE_URL,
            secret_key=app_settings.PAYSTACK_SECRET_KEY,
            public_key=app_settings.PAYSTACK_PUBLIC_KEY,
            merchant_email=app_settings.PAYSTACK_MERCHANT_EMAIL,
        )
    )


def _get_card_service(
    session: AsyncSession = Depends(get_db),
    paystack: PaystackService = Depends(_get_paystack),
) -> CardService:
    return CardService(session, paystack)


from app.enums.paystack import PAYSTACK_METADATA_CONDITION
from app.repository.transaction_repository import (
    TransactionRepository,
    TransactionAuditRepository,
)


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    openapi_extra=WEBHOOK_OPENAPI_EXTRA,
)
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(
        default="", alias="x-paystack-signature", example=_EXAMPLE_SIGNATURE
    ),
    service: CardService = Depends(_get_card_service),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Paystack webhook — verifies HMAC-SHA512 signature then processes card events.

    In DEBUG mode the signature check is skipped so you can test via Swagger.
    """
    body = await request.body()

    if not app_settings.DEBUG:
        expected = hmac.new(
            app_settings.PAYSTACK_SECRET_KEY.encode(),
            body,
            hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(expected, x_paystack_signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature"
            )

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON"
        )

    event = payload.get("event", "")
    data = payload.get("data", {})

    print(f"Received Paystack webhook event: {event}, data: {data}")

    if event == "charge.success":
        await _handle_charge_success(data, service)

    elif event in ("refund.pending", "refund.processed", "refund.failed"):
        await _handle_refund_event(event, data, session)

    return {"status": "ok"}


async def _handle_charge_success(data: dict, service: CardService) -> None:
    authorization = data.get("authorization", {})
    if not authorization.get("reusable"):
        return

    customer = data.get("customer", {})
    webhook_condition = (data.get("metadata") or {}).get("webhook_condition")
    user_id = (data.get("metadata") or {}).get("extra_data", {}).get("user_id")

    if webhook_condition == PAYSTACK_METADATA_CONDITION.CARD_APPROVED.value and user_id:
        await service.save_card_from_webhook(
            user_id=user_id,
            authorization_code=authorization["authorization_code"],
            email=customer.get("email") or "",
            last4=authorization.get("last4", ""),
            card_type=authorization.get("card_type", ""),
            bank=authorization.get("bank", ""),
            paystack_customer_code=customer.get("customer_code"),
        )


async def _handle_refund_event(
    event: str,
    data: dict,
    session: AsyncSession,
) -> None:
    paystack_reference = data.get("transaction_reference") or data.get("reference")
    if not paystack_reference:
        _log.warning("Refund webhook missing transaction_reference: %s", data)
        return

    tx_repo = TransactionRepository(session)
    audit_repo = TransactionAuditRepository(session)

    transaction = await tx_repo.get_by_paystack_reference(paystack_reference)
    if transaction is None:
        _log.warning(
            "Refund webhook: no transaction found for paystack_reference=%s",
            paystack_reference,
        )
        return

    event_type_map = {
        "refund.pending": "REFUND_PENDING",
        "refund.processed": "REFUND_CONFIRMED",
        "refund.failed": "REFUND_FAILED",
    }
    audit_event = event_type_map[event]

    metadata = {
        "paystack_reference": paystack_reference,
        "refund_amount_kobo": data.get("amount"),
        "currency": data.get("currency"),
        "refund_status": data.get("status"),
    }

    if event == "refund.failed":
        _log.error(
            "Paystack refund FAILED via webhook for txn=%s paystack_ref=%s — manual action required",
            transaction.id,
            paystack_reference,
        )
        metadata["failure_reason"] = data.get("message") or "Paystack refund failed"

    await audit_repo.create_audit(
        transaction_id=transaction.id,
        event_type=audit_event,
        previous_status=str(transaction.status),
        new_status=str(transaction.status),
        metadata=metadata,
        actor="paystack-webhook",
    )
    await session.commit()
