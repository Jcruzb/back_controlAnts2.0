from django.db.models import Count, Q, Window

from core.assistant.dto import ExpenseListItemDTO, PeriodDTO
from core.assistant.errors import InvalidArgumentsError, ResourceNotFoundError
from core.assistant.tools.base import (
    BaseReadTool,
    ToolMetadata,
    validate_limit,
    validate_period,
)
from core.models import Category, Expense, Profile


class ListMonthlyExpensesTool(BaseReadTool):
    metadata = ToolMetadata(
        name="list_monthly_expenses",
        description="Lista gastos del mes con filtros familiares y un límite acotado.",
        input_schema={
            "type": "object",
            "properties": {
                "year": {"type": "integer", "minimum": 1, "maximum": 9999},
                "month": {"type": "integer", "minimum": 1, "maximum": 12},
                "category_id": {"type": ["integer", "null"]},
                "payer_id": {"type": ["integer", "null"]},
                "planned": {"type": ["boolean", "null"]},
                "ordering": {"enum": ["-amount", "amount", "-date", "date"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["year", "month"],
            "additionalProperties": False,
        },
        output_type="ExpenseListItem[]",
    )
    allowed_arguments = (
        "year",
        "month",
        "category_id",
        "payer_id",
        "planned",
        "ordering",
        "limit",
    )

    def _execute(self, *, actor, family, arguments):
        year, month = validate_period(arguments)
        limit = validate_limit(arguments.get("limit"), default=20, maximum=100)
        ordering = arguments.get("ordering", "-amount")
        if ordering not in {"-amount", "amount", "-date", "date"}:
            raise InvalidArgumentsError(
                "La ordenación no está permitida.",
                details={"field": "ordering"},
            )

        queryset = Expense.objects.filter(
            month__family=family,
            month__year=year,
            month__month=month,
        ).select_related("category", "payer", "payer__profile")

        category_id = arguments.get("category_id")
        if category_id is not None:
            if isinstance(category_id, bool) or not isinstance(category_id, int):
                raise InvalidArgumentsError(
                    "La categoría debe ser un identificador entero.",
                    details={"field": "category_id"},
                )
            if not Category.objects.filter(id=category_id, family=family).exists():
                raise ResourceNotFoundError("La categoría solicitada no existe.")
            queryset = queryset.filter(category_id=category_id)

        payer_id = arguments.get("payer_id")
        if payer_id is not None:
            if isinstance(payer_id, bool) or not isinstance(payer_id, int):
                raise InvalidArgumentsError(
                    "El pagador debe ser un identificador entero.",
                    details={"field": "payer_id"},
                )
            if not Profile.objects.filter(
                user_id=payer_id,
                family=family,
                user__is_active=True,
            ).exists():
                raise ResourceNotFoundError("El pagador solicitado no existe.")
            queryset = queryset.filter(payer_id=payer_id)

        planned = arguments.get("planned")
        if planned is not None and not isinstance(planned, bool):
            raise InvalidArgumentsError(
                "El filtro planned debe ser booleano o null.",
                details={"field": "planned"},
            )
        planned_q = (
            Q(planned_expense__isnull=False)
            | Q(planned_expense_plan__isnull=False)
            | Q(recurring_payment__isnull=False)
        )
        if planned is True:
            queryset = queryset.filter(planned_q)
        elif planned is False:
            queryset = queryset.exclude(planned_q)

        tie_breakers = ("-date", "-id") if ordering in {"-amount", "amount"} else ("-id",)
        queryset = queryset.annotate(
            _assistant_total_count=Window(expression=Count("id"))
        )
        rows = list(queryset.order_by(ordering, *tie_breakers)[:limit])
        total_count = rows[0]._assistant_total_count if rows else 0
        has_more = total_count > limit
        return {
            "period": PeriodDTO.create(year=year, month=month).__dict__,
            "items": [ExpenseListItemDTO.from_expense(item).to_dict() for item in rows],
            "count": len(rows),
            "total_count": total_count,
            "has_more": has_more,
            "limit": limit,
        }
