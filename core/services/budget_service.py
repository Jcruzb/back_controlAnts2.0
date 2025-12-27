from datetime import date
from calendar import monthrange
from django.db.models import Sum, Q


from core.models import (
    Month,
    Expense,
    PlannedExpense,
    RecurringPayment,
)
from core.services.budget_rules import WARNING_THRESHOLD, OVER_THRESHOLD


class BudgetService:
    def __init__(self, *, family, year, month):
        self.family = family
        self.year = year
        self.month = month

    def get_month(self):
        return Month.objects.get(
            family=self.family,
            year=self.year,
            month=self.month,
        )

    def _calculate_status(self, planned, spent):
        if planned == 0:
            return "ok", 0, planned

        ratio = spent / planned

        if ratio >= OVER_THRESHOLD:
            return "over", ratio, planned - spent
        if ratio >= WARNING_THRESHOLD:
            return "warning", ratio, planned - spent

        return "ok", ratio, planned - spent

    def get_active_recurring_payments(self):
        month_start = date(self.year, self.month, 1)
        month_end = date(
            self.year,
            self.month,
            monthrange(self.year, self.month)[1]
        )

        return RecurringPayment.objects.filter(
            family=self.family,
            active=True,
            start_date__lte=month_end,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=month_start)
        )
    def get_recurring_summary(self):
        recurrences = self.get_active_recurring_payments()
        result = []

        for rec in recurrences:
            spent = (
                Expense.objects.filter(
                    recurring_payment=rec,
                    month__year=self.year,
                    month__month=self.month,
                ).aggregate(total=Sum("amount"))["total"]
                or 0
            )

            status, ratio, remaining = self._calculate_status(rec.amount, spent)

            result.append({
                "id": rec.id,
                "name": rec.name,
                "planned_amount": rec.amount,
                "spent_amount": spent,
                "remaining_amount": remaining,
                "percentage_used": round(ratio * 100, 2),
                "status": status,
            })

        return result

    def get_planned_expenses_summary(self):
        planned = PlannedExpense.objects.filter(
            family=self.family,
            month__year=self.year,
            month__month=self.month,
        )

        result = []
        for p in planned:
            spent = p.expenses.aggregate(total=Sum("amount"))["total"] or 0

            status, ratio, remaining = self._calculate_status(p.planned_amount, spent)

            result.append({
                "id": p.id,
                "category": p.category.name,
                "planned_amount": p.planned_amount,
                "spent_amount": spent,
                "remaining_amount": remaining,
                "percentage_used": round(ratio * 100, 2),
                "status": status,
            })

        return result

    def get_unplanned_expenses_total(self):
        return (
            Expense.objects.filter(
                month__year=self.year,
                month__month=self.month,
                planned_expense__isnull=True,
                recurring_payment__isnull=True,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

    def build_budget(self):
        # Validamos que el mes exista
        self.get_month()

        recurring = self.get_recurring_summary()
        planned = self.get_planned_expenses_summary()
        unplanned_total = self.get_unplanned_expenses_total()

        total_planned = sum(r["planned_amount"] for r in recurring) + sum(
            p["planned_amount"] for p in planned
        )
        total_spent = sum(r["spent_amount"] for r in recurring) + sum(
            p["spent_amount"] for p in planned
        ) + unplanned_total

        status, ratio, remaining = self._calculate_status(total_planned, total_spent)

        return {
            "year": self.year,
            "month": self.month,
            "status": status,
            "percentage_used": round(ratio * 100, 2),
            "remaining_amount": remaining,
            "recurring": recurring,
            "planned": planned,
            "unplanned_total": unplanned_total,
            "total_planned": total_planned,
            "total_spent": total_spent,
        }