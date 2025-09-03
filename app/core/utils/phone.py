from typing import Optional

import phonenumbers


def to_e164(raw: str, default_region: str = "DE") -> str:
    """Normalize a raw phone number to E.164 format (e.g., +491234567890).

    Args:
        raw: The raw phone number input from the user.
        default_region: Region to assume if the number is provided without a country code.

    Returns:
        The E.164 formatted phone number string.

    Raises:
        ValueError: If the phone number cannot be parsed or is invalid for the given region.
    """
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError(str(exc))

    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Invalid phone number")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def try_to_e164(raw: str, default_region: str = "DE") -> Optional[str]:
    """Best-effort normalization; returns None if invalid instead of raising."""
    try:
        return to_e164(raw, default_region)
    except Exception:
        return None


