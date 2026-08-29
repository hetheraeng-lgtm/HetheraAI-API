import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.paystack import PAYSTACK_METADATA_CONDITION
from app.model.user_card import UserCard
from app.repository.card_repository import CardRepository
from app.utils.libs.paystack.interfaces import (
    PaystackMetadata,
    PaystackOptions,
    RedirectToPaymentBody,
)
from app.utils.libs.paystack.service import PaystackService


class CardService:

    def __init__(self, session: AsyncSession, paystack: PaystackService) -> None:
        self.session = session
        self.paystack = paystack
        self.card_repo = CardRepository(session)

    async def initialize_card_authorization(
        self,
        user_id: uuid.UUID,
        email: str,
        callback_url: str | None = None,
    ) -> dict:
        """Generate a Paystack authorization URL. User visits it to authorize their card.
        On success Paystack calls our webhook with the authorization_code.
        """
        from app.config import app_settings

        body = RedirectToPaymentBody(
            amount=50.0,  # Minimal charge for card authorization (₦50 — refunded)
            email=email,
            callback_url=callback_url or app_settings.PAYSTACK_CALLBACK_URL,
            metadata=PaystackMetadata(
                webhook_condition=PAYSTACK_METADATA_CONDITION.CARD_APPROVED.value,
                extra_data={
                    "user_id": str(user_id),
                },
            ),
        )

        response = await self.paystack.redirect_to_payment(body)

        if not response:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not initialize card authorization. Try again.",
            )

        data = response.get("data", {})

        return {
            "authorization_url": data.get("authorization_url"),
            "access_code": data.get("access_code"),
            "reference": data.get("reference"),
        }

    async def save_card_from_webhook(
        self,
        user_id: uuid.UUID,
        authorization_code: str,
        email: str,
        last4: str,
        card_type: str,
        bank: str,
        paystack_customer_code: str | None = None,
    ) -> UserCard:
        """Called from the Paystack webhook handler when a card is authorized.
        Replaces any existing card — only one card allowed per user.
        """

        existing = await self.card_repo.get_by_authorization_code(
            user_id, authorization_code
        )

        if existing:
            return existing  # idempotent — same card re-authorized

        # Hard-delete the old card; transaction FKs are SET NULL automatically
        await self.card_repo.delete_by_user_id(user_id)

        card = UserCard(
            user_id=user_id,
            authorization_code=authorization_code,
            email=email,
            last4=last4,
            card_type=card_type,
            bank=bank,
            paystack_customer_code=paystack_customer_code,
        )

        await self.card_repo.add(card)
        await self.session.commit()
        await self.session.refresh(card)

        return card

    async def get_card(self, user_id: uuid.UUID) -> UserCard | None:
        return await self.card_repo.get_user_card(user_id)

    async def delete_card(self, user_id: uuid.UUID) -> None:
        card = await self.card_repo.get_user_card(user_id)

        if card is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No card found"
            )

        await self.card_repo.delete_by_user_id(user_id)
        await self.session.commit()
