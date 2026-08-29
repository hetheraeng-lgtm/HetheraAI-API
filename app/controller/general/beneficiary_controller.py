import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.repository.user_repository import UserRepository
from app.schema.common import ApiResponse, ChatIdPath
from app.schema.transaction import (
    BeneficiaryCreateRequest,
    BeneficiaryResponse,
    BeneficiaryUpdateRequest,
)
from app.service.beneficiary_service import BeneficiaryService

router = APIRouter(prefix="/beneficiaries", tags=["Beneficiaries"])


def _get_beneficiary_service(
    session: AsyncSession = Depends(get_db),
) -> BeneficiaryService:
    return BeneficiaryService(session)


@router.get(
    "/{chat_id}",
    response_model=ApiResponse[list[BeneficiaryResponse]],
    status_code=status.HTTP_200_OK,
    summary="List beneficiaries",
    description="List saved beneficiaries for a user, optionally filtered by service_type.",
)
async def list_beneficiaries(
    chat_id: ChatIdPath,
    service_type: str | None = None,
    service: BeneficiaryService = Depends(_get_beneficiary_service),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[list[BeneficiaryResponse]]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    items = await service.list_beneficiaries(user.id, service_type)

    return ApiResponse(
        message="Beneficiaries retrieved",
        data=[BeneficiaryResponse.model_validate(b) for b in items],
    )


@router.post(
    "/{chat_id}",
    response_model=ApiResponse[BeneficiaryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add beneficiary",
    description="Save a new beneficiary for quick future purchases.",
)
async def add_beneficiary(
    chat_id: ChatIdPath,
    payload: BeneficiaryCreateRequest,
    service: BeneficiaryService = Depends(_get_beneficiary_service),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[BeneficiaryResponse]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    b = await service.add_beneficiary(
        user_id=user.id,
        name=payload.name,
        identifier=payload.identifier,
        service_type=payload.service_type,
        service_id=payload.service_id,
    )

    return ApiResponse(
        message="Beneficiary added", data=BeneficiaryResponse.model_validate(b)
    )


@router.put(
    "/{chat_id}/{beneficiary_id}",
    response_model=ApiResponse[BeneficiaryResponse],
    status_code=status.HTTP_200_OK,
    summary="Update beneficiary",
    description="Update the name, identifier, or service_id of a saved beneficiary.",
)
async def update_beneficiary(
    chat_id: ChatIdPath,
    beneficiary_id: uuid.UUID,
    payload: BeneficiaryUpdateRequest,
    service: BeneficiaryService = Depends(_get_beneficiary_service),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[BeneficiaryResponse]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    b = await service.update_beneficiary(
        user_id=user.id,
        beneficiary_id=beneficiary_id,
        name=payload.name,
        identifier=payload.identifier,
        service_id=payload.service_id,
    )

    return ApiResponse(
        message="Beneficiary updated", data=BeneficiaryResponse.model_validate(b)
    )


@router.delete(
    "/{chat_id}/{beneficiary_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete beneficiary",
    description="Soft-delete a saved beneficiary.",
)
async def delete_beneficiary(
    chat_id: ChatIdPath,
    beneficiary_id: uuid.UUID,
    service: BeneficiaryService = Depends(_get_beneficiary_service),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[None]:
    user = await UserRepository(session).get_by_chat_id(chat_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await service.delete_beneficiary(user.id, beneficiary_id)

    return ApiResponse(message="Beneficiary removed")
