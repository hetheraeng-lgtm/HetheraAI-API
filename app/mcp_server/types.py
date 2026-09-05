from typing import Annotated

from pydantic import Field

ChatId = Annotated[
    str,
    Field(
        description="Chat ID that uniquely identifies the acting user.",
        examples=["08119995541"],
    ),
]
