import phonenumbers
from fastapi import HTTPException, status


def validate_nigerian_phone(phone: str) -> str:
    """Parse and validate a Nigerian phone number. Returns E.164 format."""
    try:
        parsed = phonenumbers.parse(phone, "NG")
    except phonenumbers.NumberParseException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid phone number: '{phone}'",
        )

    if not phonenumbers.is_valid_number(parsed):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phone number '{phone}' is not a valid Nigerian number",
        )

    region = phonenumbers.region_code_for_number(parsed)

    if region != "NG":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Nigerian phone numbers are supported",
        )

    return phone
    # return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
