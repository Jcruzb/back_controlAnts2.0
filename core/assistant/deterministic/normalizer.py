from dataclasses import dataclass
from datetime import date
import re
import unicodedata

from django.conf import settings
from django.utils import timezone

from core.assistant.errors import AmbiguousPeriodError, InvalidPeriodError
from core.assistant.visual_contract.formatting import build_period


MONTH_NAMES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


@dataclass(frozen=True)
class ResolvedPeriod:
    year: int
    month: int
    label: str
    timezone: str

    def to_dict(self):
        return {
            "year": self.year,
            "month": self.month,
            "label": self.label,
            "timezone": self.timezone,
        }


def normalize_text(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def current_local_date():
    return timezone.localtime(timezone.now(), timezone.get_default_timezone()).date()


def previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def shift_month(year, month, offset):
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def resolve_period_from_arguments(arguments):
    if not isinstance(arguments, dict) or set(arguments).difference({"year", "month"}):
        raise InvalidPeriodError()
    year = arguments.get("year")
    month = arguments.get("month")
    if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
        raise InvalidPeriodError(details={"field": "year"})
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise InvalidPeriodError(details={"field": "month"})
    return ResolvedPeriod(**build_period(year=year, month=month, timezone_name=settings.TIME_ZONE))


def resolve_period(message, *, reference_date=None):
    normalized = normalize_text(message)
    reference_date = reference_date or current_local_date()
    relative_current = any(phrase in normalized for phrase in ("este mes", "mes actual"))
    relative_previous = any(phrase in normalized for phrase in ("mes pasado", "mes anterior"))
    if relative_current and relative_previous:
        raise AmbiguousPeriodError()

    found_names = []
    for name, month in MONTH_NAMES.items():
        if re.search(rf"\b{name}\b", normalized):
            found_names.append((name, month))
    distinct_months = {month for _, month in found_names}
    if len(distinct_months) > 1:
        raise AmbiguousPeriodError()

    year = reference_date.year
    month = reference_date.month
    if relative_previous:
        year, month = previous_month(year, month)
    elif found_names:
        month = found_names[0][1]
        explicit_years = re.findall(r"\b(?:19|20)\d{2}\b", normalized)
        if len(set(explicit_years)) > 1:
            raise AmbiguousPeriodError()
        if explicit_years:
            year = int(explicit_years[0])
        # A month without year always resolves inside the current calendar
        # year. This is deterministic for both past and upcoming months.
        if relative_current and month != reference_date.month:
            raise AmbiguousPeriodError()

    return ResolvedPeriod(**build_period(year=year, month=month, timezone_name=settings.TIME_ZONE))
