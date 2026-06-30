from datetime import date
from calendar import monthrange
from decimal import Decimal
from django.db.models import Sum, Q


from core.models import (
    Month,
    Expense,
    PlannedExpense,
    PlannedExpensePlan,
    PlannedExpenseVersion,
    RecurringPayment,
    RecurringPaymentOccurrence,
)
from core.serializers.category_serializer import CategorySerializer
from core.services.budget_rules import WARNING_THRESHOLD, OVER_THRESHOLD
from core.services.recurring_payment_service import (
    calculate_recurring_payment_amounts,
)


class BudgetService:
    def __init__(self, *, family, year, month):
        self.family = family
        self.year = year
        self.month = month

    def get_month(self):
        month, _ = Month.objects.get_or_create(
            family=self.family,
            year=self.year,
            month=self.month,
            defaults={
                "is_closed": False,
            }
        )
        return month

    def _calculate_status(self, planned, spent):
        if planned == 0:
            return "ok", 0, planned

        ratio = spent / planned

        if ratio >= OVER_THRESHOLD:
            return "over", ratio, planned - spent
        if ratio >= WARNING_THRESHOLD:
            return "warning", ratio, planned - spent

        return "ok", ratio, planned - spent

    def _serialize_category(self, category):
        return {
            "category": category.id,
            "category_name": category.name,
            "category_detail": CategorySerializer(category).data,
        }

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
        ).select_related("category", "payer", "payer__profile")

    def get_recurring_summary(self):
        recurrences = list(self.get_active_recurring_payments())
        month_obj = self.get_month()
        existing_occurrences = {
            occurrence.recurring_payment_id: occurrence
            for occurrence in RecurringPaymentOccurrence.objects.filter(
                recurring_payment__in=recurrences,
                month=month_obj,
            )
        }
        missing_occurrences = [
            RecurringPaymentOccurrence(
                recurring_payment=recurrence,
                month=month_obj,
            )
            for recurrence in recurrences
            if recurrence.id not in existing_occurrences
        ]
        if missing_occurrences:
            RecurringPaymentOccurrence.objects.bulk_create(
                missing_occurrences,
                ignore_conflicts=True,
            )
            existing_occurrences = {
                occurrence.recurring_payment_id: occurrence
                for occurrence in RecurringPaymentOccurrence.objects.filter(
                    recurring_payment__in=recurrences,
                    month=month_obj,
                )
            }
        recurring_totals = {
            row["recurring_payment"]: row["total"] or 0
            for row in (
                Expense.objects.filter(
                    recurring_payment__in=recurrences,
                    month__family=self.family,
                    month__year=self.year,
                    month__month=self.month,
                )
                .values("recurring_payment")
                .annotate(total=Sum("amount"))
            )
        }
        result = []

        for rec in recurrences:
            spent = recurring_totals.get(rec.id, 0)
            occurrence = existing_occurrences[rec.id]
            amounts = calculate_recurring_payment_amounts(
                planned_amount=rec.amount,
                paid_amount=spent,
                is_completed=occurrence.is_completed,
            )

            status, ratio, _ = self._calculate_status(
                amounts.planned_amount,
                amounts.paid_amount,
            )

            result.append({
                "id": rec.id,
                "occurrence_id": occurrence.id,
                "name": rec.name,
                **self._serialize_category(rec.category),
                "payer": rec.payer_id,
                "payer_detail": self._serialize_payer(rec.payer),
                "planned_amount": amounts.planned_amount,
                "paid_amount": amounts.paid_amount,
                "pending_amount": amounts.pending_amount,
                "difference_amount": amounts.difference_amount,
                "is_completed": amounts.is_completed,
                "payment_status": amounts.payment_status,
                # Backwards-compatible aliases. ``remaining_amount`` now has
                # the unambiguous obligation semantics requested by the API.
                "spent_amount": amounts.paid_amount,
                "remaining_amount": amounts.pending_amount,
                "percentage_used": round(ratio * 100, 2),
                "status": status,
            })

        return result

    def _serialize_payer(self, payer):
        if payer is None:
            return None

        full_name = payer.get_full_name().strip()
        role = getattr(getattr(payer, "profile", None), "role", None)
        return {
            "id": payer.id,
            "username": payer.username,
            "first_name": payer.first_name,
            "last_name": payer.last_name,
            "email": payer.email,
            "display_name": full_name or payer.username,
            "role": role,
        }

    def get_planned_plans_summary(self):
        """
        Returns planned expenses coming from PlannedExpensePlan (new system)
        for the given month, excluding ONE_MONTH plans to avoid duplication
        with legacy PlannedExpense.
        """
        month_obj = self.get_month()

        plans = PlannedExpensePlan.objects.filter(
            family=self.family,
            active=True,
            plan_type="ONGOING",
            start_month__lte=month_obj,
        ).filter(
            Q(end_month__isnull=True) | Q(end_month__gte=month_obj)
        ).select_related("category")

        category_ids = [plan.category_id for plan in plans]
        category_totals = {
            row["category"]: row["total"] or 0
            for row in (
                Expense.objects.filter(
                    month__family=self.family,
                    month__year=self.year,
                    month__month=self.month,
                    category_id__in=category_ids,
                )
                .values("category")
                .annotate(total=Sum("amount"))
            )
        }

        result = []

        for plan in plans:
            version = (
                PlannedExpenseVersion.objects.filter(
                    plan=plan,
                    valid_from__lte=month_obj,
                )
                .filter(
                    Q(valid_to__isnull=True) | Q(valid_to__gte=month_obj)
                )
                .order_by("-valid_from")
                .first()
            )

            if not version:
                continue

            spent = category_totals.get(plan.category_id, 0)

            status, ratio, remaining = self._calculate_status(
                version.planned_amount,
                spent,
            )

            result.append({
                "id": f"plan-{plan.id}",
                **self._serialize_category(plan.category),
                "planned_amount": version.planned_amount,
                "spent_amount": spent,
                "remaining_amount": remaining,
                "percentage_used": round(ratio * 100, 2),
                "status": status,
                "source": "plan",
            })

        return result

    def get_planned_expenses_summary(self):
        planned = PlannedExpense.objects.filter(
            family=self.family,
            month__year=self.year,
            month__month=self.month,
        ).select_related("category").annotate(spent_total=Sum("expenses__amount"))

        result = []
        for p in planned:
            spent = p.spent_total or 0

            status, ratio, remaining = self._calculate_status(p.planned_amount, spent)

            result.append({
                "id": p.id,
                **self._serialize_category(p.category),
                "planned_amount": p.planned_amount,
                "spent_amount": spent,
                "remaining_amount": remaining,
                "percentage_used": round(ratio * 100, 2),
                "status": status,
            })

        return result

    def get_unplanned_expenses_total(self):
        total = (
            Expense.objects.filter(
                month__family=self.family,
                month__year=self.year,
                month__month=self.month,
                planned_expense__isnull=True,
                recurring_payment__isnull=True,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        return Decimal(total).quantize(Decimal("0.01"))

    def build_budget(self):
        month = self.get_month()
        recurring = self.get_recurring_summary()
        planned_legacy = self.get_planned_expenses_summary()
        planned_plans = self.get_planned_plans_summary()
        planned = planned_legacy + planned_plans

        unplanned_total = self.get_unplanned_expenses_total()

        total_planned = sum(r["planned_amount"] for r in recurring) + sum(
            p["planned_amount"] for p in planned
        )
        total_spent = sum(r["spent_amount"] for r in recurring) + sum(
            p["spent_amount"] for p in planned
        ) + unplanned_total

        status, ratio, remaining = self._calculate_status(total_planned, total_spent)
        recurring_pending_amount = sum(r["pending_amount"] for r in recurring)
        planned_pending_amount = sum(
            max(p["remaining_amount"], 0) for p in planned
        )

        return {
            "month_id": month.id,
            "year": self.year,
            "month": self.month,
            "status": status,
            "percentage_used": round(ratio * 100, 2),
            "remaining_amount": remaining,
            "difference_amount": remaining,
            "recurring_pending_amount": recurring_pending_amount,
            "total_pending_amount": recurring_pending_amount + planned_pending_amount,
            "recurring": recurring,
            "planned": planned,
            "unplanned_total": unplanned_total,
            "total_planned": total_planned,
            "total_spent": total_spent,
        }
