from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum

from core.assistant.dto import (
    PayerSpendingSummaryDTO,
    PeriodDTO,
    money_string,
    percentage_string,
)
from core.assistant.tools.base import BaseReadTool, ToolMetadata, validate_period
from core.models import Expense


class GetPayerSpendingTool(BaseReadTool):
    metadata = ToolMetadata(
        name="get_payer_spending",
        description="Agrupa el gasto real mensual por pagador de la familia.",
        input_schema={
            "type": "object",
            "properties": {
                "year": {"type": "integer", "minimum": 1, "maximum": 9999},
                "month": {"type": "integer", "minimum": 1, "maximum": 12},
            },
            "required": ["year", "month"],
            "additionalProperties": False,
        },
        output_type="PayerSpendingSummary[]",
    )
    allowed_arguments = ("year", "month")

    def _execute(self, *, actor, family, arguments):
        year, month = validate_period(arguments)
        base = Expense.objects.filter(
            month__family=family,
            month__year=year,
            month__month=month,
        )
        grand_total = Decimal(base.aggregate(total=Sum("amount"))["total"] or 0)
        rows = list(
            base.values(
                "payer_id",
                "payer__username",
                "payer__first_name",
                "payer__last_name",
            )
            .annotate(amount=Sum("amount"), count=Count("id"))
            .order_by("-amount", "payer_id")[:101]
        )
        has_more = len(rows) > 100
        rows = rows[:100]
        items = []
        for row in rows:
            amount = Decimal(row["amount"] or 0)
            full_name = " ".join(
                part for part in (row["payer__first_name"], row["payer__last_name"]) if part
            ).strip()
            display_name = full_name or row["payer__username"] or "Sin asignar"
            percentage = (amount / grand_total * Decimal("100")) if grand_total else Decimal("0")
            items.append(
                PayerSpendingSummaryDTO(
                    payer_id=row["payer_id"],
                    display_name=display_name,
                    amount=money_string(amount),
                    count=row["count"],
                    percentage=percentage_string(percentage),
                ).to_dict()
            )
        return {
            "period": PeriodDTO.create(year=year, month=month).__dict__,
            "currency": settings.DEFAULT_CURRENCY,
            "total": money_string(grand_total),
            "items": items,
            "count": len(items),
            "has_more": has_more,
            "limit": 100,
        }

