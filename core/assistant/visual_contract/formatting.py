from decimal import Decimal, ROUND_HALF_UP

from core.assistant.dto import PeriodDTO, money_string


CURRENCY_SYMBOLS = {"EUR": "€"}


def format_currency(value, currency="EUR"):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    raw = f"{amount:,.2f}"
    localized = raw.replace(",", "_").replace(".", ",").replace("_", ".")
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{localized} {symbol}"


def format_percentage(value):
    amount = Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{str(amount).replace('.', ',')} %"


def build_period(*, year, month, timezone_name):
    period = PeriodDTO.create(year=year, month=month)
    return {
        "year": period.year,
        "month": period.month,
        "label": period.label,
        "timezone": timezone_name,
    }


def decimal_string(value):
    return money_string(value)
