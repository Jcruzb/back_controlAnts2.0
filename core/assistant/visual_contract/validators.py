import re
from decimal import Decimal, InvalidOperation

from core.assistant.errors import InvalidVisualBlockError


DECIMAL_PATTERN = re.compile(r"^-?\d+(?:\.\d{2})$")
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_\-]{0,63}$")


def require_mapping(value, *, field="block", error_type=InvalidVisualBlockError):
    if not isinstance(value, dict):
        raise error_type(details={"field": field})
    return value


def require_list(value, *, field, error_type=InvalidVisualBlockError):
    if not isinstance(value, list):
        raise error_type(details={"field": field})
    return value


def require_string(value, *, field, maximum=None, allow_blank=False, error_type=InvalidVisualBlockError):
    if not isinstance(value, str) or (not allow_blank and not value.strip()):
        raise error_type(details={"field": field})
    if maximum is not None and len(value) > maximum:
        raise error_type(details={"field": field, "maximum": maximum})
    return value


def require_id(value, *, field="id", error_type=InvalidVisualBlockError):
    require_string(value, field=field, maximum=64, error_type=error_type)
    if ID_PATTERN.fullmatch(value) is None:
        raise error_type(details={"field": field})
    return value


def require_enum(value, enum_type, *, field, error_type=InvalidVisualBlockError):
    if value not in enum_type.values():
        raise error_type(details={"field": field, "allowed": sorted(enum_type.values())})
    return value


def require_decimal_string(value, *, field, error_type=InvalidVisualBlockError):
    if not isinstance(value, str) or DECIMAL_PATTERN.fullmatch(value) is None:
        raise error_type(details={"field": field, "expected": "decimal_string"})
    try:
        Decimal(value)
    except InvalidOperation:
        raise error_type(details={"field": field, "expected": "decimal_string"})
    return value


def reject_unknown_fields(payload, *, allowed, error_type=InvalidVisualBlockError):
    unknown = set(payload).difference(allowed)
    if unknown:
        raise error_type(details={"field": sorted(unknown)[0]})


def require_fields(payload, *, required, error_type=InvalidVisualBlockError):
    missing = set(required).difference(payload)
    if missing:
        raise error_type(details={"field": sorted(missing)[0]})
