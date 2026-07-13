from django.db.models import Q, Sum

from core.models import Expense, PlannedExpenseOccurrence, PlannedExpenseVersion
from core.services.recurring_payment_service import calculate_recurring_payment_amounts


def _month_lte(prefix, month):
    return Q(**{f"{prefix}__year__lt": month.year}) | Q(
        **{f"{prefix}__year": month.year, f"{prefix}__month__lte": month.month}
    )


def _month_gte(prefix, month):
    return Q(**{f"{prefix}__year__gt": month.year}) | Q(
        **{f"{prefix}__year": month.year, f"{prefix}__month__gte": month.month}
    )


def get_planned_payment_version(*, planned_expense_plan, month):
    return (
        PlannedExpenseVersion.objects.filter(plan=planned_expense_plan)
        .filter(_month_lte("valid_from", month))
        .filter(Q(valid_to__isnull=True) | _month_gte("valid_to", month))
        .order_by("-valid_from__year", "-valid_from__month", "-created_at")
        .first()
    )


def get_or_create_planned_expense_occurrence(
    *, month, planned_expense=None, planned_expense_plan=None
):
    if (planned_expense is None) == (planned_expense_plan is None):
        raise ValueError("Exactly one planned payment source is required")

    lookup = {"month": month}
    if planned_expense is not None:
        if planned_expense.month_id != month.id:
            raise ValueError("Planned expense does not apply to the selected month")
        lookup["planned_expense"] = planned_expense
    else:
        starts_after = (
            planned_expense_plan.start_month.year,
            planned_expense_plan.start_month.month,
        ) > (month.year, month.month)
        ends_before = planned_expense_plan.end_month is not None and (
            planned_expense_plan.end_month.year,
            planned_expense_plan.end_month.month,
        ) < (month.year, month.month)
        if starts_after or ends_before:
            raise ValueError("Planned expense plan does not apply to the selected month")
        lookup["planned_expense_plan"] = planned_expense_plan

    occurrence, _ = PlannedExpenseOccurrence.objects.get_or_create(**lookup)
    return occurrence


def get_planned_payment_month_state(
    *, month, planned_expense=None, planned_expense_plan=None
):
    occurrence = get_or_create_planned_expense_occurrence(
        month=month,
        planned_expense=planned_expense,
        planned_expense_plan=planned_expense_plan,
    )

    if planned_expense is not None:
        planned_amount = planned_expense.planned_amount
        expense_filter = {"planned_expense": planned_expense}
    else:
        version = get_planned_payment_version(
            planned_expense_plan=planned_expense_plan,
            month=month,
        )
        if version is None:
            raise ValueError("Planned expense plan has no version for the selected month")
        planned_amount = version.planned_amount
        expense_filter = {"planned_expense_plan": planned_expense_plan}

    paid_amount = (
        Expense.objects.filter(month=month, **expense_filter).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    amounts = calculate_recurring_payment_amounts(
        planned_amount=planned_amount,
        paid_amount=paid_amount,
        is_completed=occurrence.is_completed,
    )
    return occurrence, amounts
