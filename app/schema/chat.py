from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=2000,
        examples=["What MTN subscription can I do with ₦200?"],
    )


class ChatResponse(BaseModel):
    reply: str = Field(
        ...,
        examples=[
            (
                "With ₦200, you can consider:\n"
                "- MTN Daily Plan — ₦100\n"
                "- MTN 2-day Plan — ₦200"
            ),
        ],
    )
