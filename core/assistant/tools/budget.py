from django.conf import settings

from core.assistant.dto import MonthlyBudgetSummaryDTO, MonthlyCashSummaryDTO
from core.assistant.tools.base import BaseReadTool, ToolMetadata, validate_period
from core.services.budget_service import BudgetService


PERIOD_SCHEMA = {
    "type": "object",
    "properties": {
        "year": {"type": "integer", "minimum": 1, "maximum": 9999},
        "month": {"type": "integer", "minimum": 1, "maximum": 12},
    },
    "required": ["year", "month"],
    "additionalProperties": False,
}


class GetMonthlyBudgetTool(BaseReadTool):
    metadata = ToolMetadata(
        name="get_monthly_budget",
        description="Obtiene el resumen presupuestario del mes para la familia autenticada.",
        input_schema=PERIOD_SCHEMA,
        output_type="MonthlyBudgetSummary",
    )
    allowed_arguments = ("year", "month")

    def _execute(self, *, actor, family, arguments):
        year, month = validate_period(arguments)
        budget = BudgetService(
            family=family,
            year=year,
            month=month,
            materialize=False,
        ).build_budget()
        return MonthlyBudgetSummaryDTO.from_budget(
            budget=budget,
            currency=settings.DEFAULT_CURRENCY,
        ).to_dict()


class GetMonthlyCashSummaryTool(BaseReadTool):
    metadata = ToolMetadata(
        name="get_monthly_cash_summary",
        description="Obtiene ingresos, salidas y saldo real de caja del mes.",
        input_schema=PERIOD_SCHEMA,
        output_type="MonthlyCashSummary",
    )
    allowed_arguments = ("year", "month")

    def _execute(self, *, actor, family, arguments):
        year, month = validate_period(arguments)
        budget = BudgetService(
            family=family,
            year=year,
            month=month,
            materialize=False,
        ).build_budget()
        return MonthlyCashSummaryDTO.from_budget(
            budget=budget,
            currency=settings.DEFAULT_CURRENCY,
        ).to_dict()
