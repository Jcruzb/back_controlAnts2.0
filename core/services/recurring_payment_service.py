from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum

from core.models import Expense, RecurringPaymentOccurrence


ZERO = Decimal("0.00")
MONEY_QUANTUM = Decimal("0.01")


def _money(value):
    if value is None:
        return ZERO
    return Decimal(value).quantize(MONEY_QUANTUM)


@dataclass(frozen=True)
class RecurringPaymentAmounts:
    planned_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal
    difference_amount: Decimal
    is_completed: bool
    payment_status: str


def calculate_recurring_payment_amounts(
    *, planned_amount, paid_amount, is_completed
):
    """Return the canonical monthly fixed-payment calculation.

    ``difference_amount`` is signed planned minus paid. ``pending_amount`` is
    an obligation and therefore is zero after manual completion and never
    negative.
    """

    planned = _money(planned_amount)
    paid = _money(paid_amount)
    difference = _money(planned - paid)

    if is_completed:
        pending = ZERO
        payment_status = "completed"
    else:
        pending = max(difference, ZERO)
        if paid > planned:
            payment_status = "exceeded"
        elif paid == planned:
            payment_status = "covered"
        elif paid > ZERO:
            payment_status = "partially_paid"
        else:
            payment_status = "pending"

    return RecurringPaymentAmounts(
        planned_amount=planned,
        paid_amount=paid,
        pending_amount=_money(pending),
        difference_amount=difference,
        is_completed=bool(is_completed),
        payment_status=payment_status,
    )


def get_or_create_recurring_payment_occurrence(*, recurring_payment, month):
    occurrence, _ = RecurringPaymentOccurrence.objects.get_or_create(
        recurring_payment=recurring_payment,
        month=month,
    )
    return occurrence


def get_recurring_payment_paid_amount(*, recurring_payment, month):
    return _money(
        Expense.objects.filter(
            recurring_payment=recurring_payment,
            month=month,
        ).aggregate(total=Sum("amount"))["total"]
    )


def get_recurring_payment_month_state(*, recurring_payment, month):
    occurrence = get_or_create_recurring_payment_occurrence(
        recurring_payment=recurring_payment,
        month=month,
    )
    paid_amount = get_recurring_payment_paid_amount(
        recurring_payment=recurring_payment,
        month=month,
    )
    amounts = calculate_recurring_payment_amounts(
        planned_amount=recurring_payment.amount,
        paid_amount=paid_amount,
        is_completed=occurrence.is_completed,
    )
    return occurrence, amounts
