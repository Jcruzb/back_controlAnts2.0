from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum

from core.assistant.dto import (
    CategorySpendingSummaryDTO,
    PeriodDTO,
    money_string,
    percentage_string,
)
from core.assistant.tools.base import (
    BaseReadTool,
    ToolMetadata,
    validate_limit,
    validate_period,
)
from core.models import Expense


class GetCategorySpendingTool(BaseReadTool):
    metadata = ToolMetadata(
        name="get_category_spending",
        description="Agrupa el gasto real mensual por categoría en el backend.",
        input_schema={
            "type": "object",
            "properties": {
                "year": {"type": "integer", "minimum": 1, "maximum": 9999},
                "month": {"type": "integer", "minimum": 1, "maximum": 12},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["year", "month"],
            "additionalProperties": False,
        },
        output_type="CategorySpendingSummary[]",
    )
    allowed_arguments = ("year", "month", "limit")

    def _execute(self, *, actor, family, arguments):
        year, month = validate_period(arguments)
        limit = validate_limit(arguments.get("limit"), default=10, maximum=50)
        base = Expense.objects.filter(
            month__family=family,
            month__year=year,
            month__month=month,
        )
        grand_total = Decimal(base.aggregate(total=Sum("amount"))["total"] or 0)
        rows = list(
            base.values("category_id", "category__name", "category__icon")
            .annotate(amount=Sum("amount"), count=Count("id"))
            .order_by("-amount", "category__name")[: limit + 1]
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = []
        for row in rows:
            amount = Decimal(row["amount"] or 0)
            percentage = (amount / grand_total * Decimal("100")) if grand_total else Decimal("0")
            items.append(
                CategorySpendingSummaryDTO(
                    category_id=row["category_id"],
                    name=row["category__name"],
                    icon=row["category__icon"],
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
            "limit": limit,
        }

