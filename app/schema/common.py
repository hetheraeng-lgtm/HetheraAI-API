from typing import Annotated, Generic, Literal, TypeVar

from fastapi import Path
from pydantic import BaseModel

T = TypeVar("T")

ChatIdPath = Annotated[str, Path(example="08119995541")]
AirtimeServiceIdPath = Annotated[str, Path(example="glo")]
MobileDataServiceIdPath = Annotated[str, Path(example="glo-data")]
CableServiceIdPath = Annotated[str, Path(example="gotv")]

CABLE_PROVIDERS = frozenset({"dstv", "gotv", "startimes"})

ELECTRICITY_PROVIDERS = frozenset(
    {
        "ikeja-electric",
        "eko-electric",
        "kano-electric",
        "portharcourt-electric",
        "jos-electric",
        "ibadan-electric",
        "abuja-electric",
        "enugu-electric",
        "benin-electric",
        "aba-electric",
        "yola-electric",
        "kaduna-electric",
    }
)


ELECTRICITY_PROVIDER_LABELS: dict[str, str] = {
    "IKEDC": "ikeja-electric",
    "EKEDC": "eko-electric",
    "KEDCO": "kano-electric",
    "PHED": "portharcourt-electric",
    "JED": "jos-electric",
    "IBEDC": "ibadan-electric",
    "KAEDCO": "kaduna-electric",
    "AEDC": "abuja-electric",
    "EEDC": "enugu-electric",
    "BEDC": "benin-electric",
    "ABA": "aba-electric",
    "YEDC": "yola-electric",
}


class ApiResponse(BaseModel, Generic[T]):
    status: Literal["success", "failed"] = "success"
    message: str
    data: T | None = None
