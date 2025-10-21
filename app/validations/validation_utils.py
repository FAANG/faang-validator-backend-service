from typing import Any, Optional, Literal
import re


def normalize_ontology_term(term_id: str) -> str:
    if not term_id:
        return term_id

    if ':' in term_id:
        return term_id

    if '_' in term_id:
        return term_id.replace('_', ':', 1)

    return term_id


def convert_term_to_obo_url(term_id: str) -> str:
    if not term_id or term_id in [
        "restricted access",
        "not applicable",
        "not collected",
        "not provided",
        ""
    ]:
        return ""

    term_colon = normalize_ontology_term(term_id)
    term_underscore = term_colon.replace(':', '_')

    return f"http://purl.obolibrary.org/obo/{term_underscore}"


def is_restricted_value(value: str) -> bool:
    if not value:
        return True

    restricted_values = {
        "restricted access",
        "not applicable",
        "not collected",
        "not provided",
        ""
    }

    return value in restricted_values


# common validation utilities for field validators
def validate_non_negative_numeric(
    v: Any,
    field_name: str = "Value",
    allow_restricted: bool = True
) -> Optional[float]:

    # empty/None values
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return None

    # restricted access
    if allow_restricted and v == "restricted access":
        return v

    try:
        numeric_val = float(v)
        if numeric_val < 0:
            raise ValueError(f"{field_name} must be non-negative, got {numeric_val}")
        return numeric_val
    except ValueError as e:
        if "non-negative" in str(e):
            raise
        raise ValueError(f"{field_name} must be a valid number, got '{v}'")


def validate_percentage(v: Any, field_name: str = "Percentage") -> None | Literal["restricted access"] | float:
    if v == "restricted access" or v is None:
        return v

    numeric_val = validate_non_negative_numeric(v, field_name, allow_restricted=True)

    if numeric_val is None or numeric_val == "restricted access":
        return numeric_val

    if not (0 <= numeric_val <= 100):
        raise ValueError(f"{field_name} must be between 0 and 100, got {numeric_val}")

    return numeric_val


def validate_latitude(v: Any) -> Optional[float]:
    if not v or (isinstance(v, str) and v.strip() == ""):
        return None

    try:
        lat_val = float(v)
        if not (-90 <= lat_val <= 90):
            raise ValueError(f"Latitude must be between -90 and 90 degrees, got {lat_val}")
        return lat_val
    except ValueError as e:
        if "between -90 and 90" in str(e):
            raise
        raise ValueError(f"Latitude must be a valid number, got '{v}'")


def validate_longitude(v: Any) -> Optional[float]:
    if not v or (isinstance(v, str) and v.strip() == ""):
        return None

    try:
        lon_val = float(v)
        if not (-180 <= lon_val <= 180):
            raise ValueError(f"Longitude must be between -180 and 180 degrees, got {lon_val}")
        return lon_val
    except ValueError as e:
        if "between -180 and 180" in str(e):
            raise
        raise ValueError(f"Longitude must be a valid number, got '{v}'")


def validate_url(
    v: Any,
    field_name: str = "URL",
    allow_restricted: bool = True,
    allowed_protocols: tuple = ('http://', 'https://')
) -> Optional[str]:
    if not v or (isinstance(v, str) and v.strip() == ""):
        return v

    if allow_restricted and v == "restricted access":
        return v

    if not any(v.startswith(protocol) for protocol in allowed_protocols):
        protocols_str = "', '".join(allowed_protocols)
        raise ValueError(
            f"{field_name} must be a valid URL starting with '{protocols_str}', got '{v}'"
        )

    return v


def validate_protocol_url(v: Any, allow_restricted: bool = True) -> Optional[str]:
    return validate_url(
        v,
        field_name="Protocol",
        allow_restricted=allow_restricted,
        allowed_protocols=('http://', 'https://', 'ftp://')
    )


def validate_date_format(
    v: Any,
    unit: Optional[str],
    field_name: str = "Date"
) -> Optional[str]:
    if not v or v in ["not applicable", "not collected", "not provided", "restricted access", ""]:
        return v

    if not unit:
        return v

    patterns = {
        "YYYY-MM-DD": r'^[12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$',
        "YYYY-MM": r'^[12]\d{3}-(0[1-9]|1[0-2])$',
        "YYYY": r'^[12]\d{3}$'
    }

    pattern = patterns.get(unit)
    if not pattern:
        return v

    if not re.match(pattern, v):
        raise ValueError(f"Invalid {field_name} format: {v}. Must match {unit} pattern")

    return v


def validate_time_format(v: Any, field_name: str = "Time") -> Optional[str]:
    if not v or v == "":
        return None

    pattern = r'^([0-1][0-9]|[2][0-3]):([0-5][0-9])$'
    if not re.match(pattern, v):
        raise ValueError(
            f"{field_name} must be in HH:MM format (00:00 to 23:59), got '{v}'"
        )

    return v


def validate_photoperiod(v: Any) -> str:
    if v in ["natural light", "restricted access"]:
        return v

    # Pattern: XXL:XXD where XX is 1-24
    pattern = r'^(2[0-4]|1[0-9]|[1-9])L:(2[0-4]|1[0-9]|[1-9])D$'
    if not re.match(pattern, v):
        raise ValueError(
            f"Photoperiod must be 'natural light' or follow pattern 'XXL:XXD' "
            f"(e.g., '12L:12D'), got '{v}'"
        )

    return v


def strip_and_convert_empty_to_none(v: Any) -> Any:
    if isinstance(v, str):
        v = v.strip()
        return None if v == "" else v
    elif v == "":
        return None
    return v


def validate_sample_name(v: Any) -> str:
    if not v or v.strip() == "":
        raise ValueError("Sample Name is required and cannot be empty")
    return v.strip()


def validate_required_field(v: Any, field_name: str) -> str:
    if not v or (isinstance(v, str) and v.strip() == ""):
        raise ValueError(f"{field_name} is required and cannot be empty")
    return v.strip() if isinstance(v, str) else v