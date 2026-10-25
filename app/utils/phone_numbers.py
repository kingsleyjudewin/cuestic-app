import phonenumbers
from phonenumbers import NumberParseException
from app.utils.errors import ValidationError


def normalize_phone_number(raw_phone: str, default_country: str = "IN") -> dict:
    """
    Validate and normalize phone number.
    default_country can be a 2-letter region ('IN', 'US') or calling code ('+91', '91').
    Returns dict with:
        - e164: '+919876543210'
        - country_code: '+91'
        - national_number: '9876543210'
        - wa_phone: '919876543210' (digits only for wa.me)
    Raises ValidationError if invalid.
    """
    if not raw_phone or not str(raw_phone).strip():
        raise ValidationError("Phone number is required.", details={"phone_number": "Cannot be empty"})
    
    clean_raw = str(raw_phone).strip()
    
    region = "IN"
    if default_country:
        clean_dc = str(default_country).strip()
        if clean_dc.startswith("+") or clean_dc.isdigit():
            try:
                numeric_code = int(clean_dc.lstrip("+"))
                reg = phonenumbers.region_code_for_country_code(numeric_code)
                if reg:
                    region = reg
            except ValueError:
                region = "IN"
        elif len(clean_dc) == 2 and clean_dc.isalpha():
            region = clean_dc.upper()

    try:
        parsed = phonenumbers.parse(clean_raw, region)
    except NumberParseException as e:
        raise ValidationError(
            f"Invalid phone number format: {str(e)}",
            details={"phone_number": clean_raw}
        )
    
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError(
            "Phone number is not valid for country code.",
            details={"phone_number": clean_raw}
        )
    
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    country_code = f"+{parsed.country_code}"
    wa_phone = e164.lstrip("+")
    
    return {
        "e164": e164,
        "country_code": country_code,
        "national_number": str(parsed.national_number),
        "wa_phone": wa_phone,
    }


def to_wa_phone(phone_number: str, default_country: str = "IN") -> str:
    """Normalize phone number to wa.me clean digit format."""
    res = normalize_phone_number(phone_number, default_country)
    return res["wa_phone"]
