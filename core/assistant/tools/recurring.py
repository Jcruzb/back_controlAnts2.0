from django.conf import settings

from core.assistant.dto import PeriodDTO, RecurringPaymentStatusDTO
from core.assistant.tools.base import BaseReadTool, ToolMetadata, validate_period
from core.services.budget_service import BudgetService


class GetRecurringPaymentStatusTool(BaseReadTool):
    metadata = ToolMetadata(
        name="get_recurring_payment_status",
        description="Obtiene los estados canónicos de pagos recurrentes del mes.",
        input_schema={
            "type": "object",
            "properties": {
                "year": {"type": "integer", "minimum": 1, "maximum": 9999},
                "month": {"type": "integer", "minimum": 1, "maximum": 12},
            },
            "required": ["year", "month"],
            "additionalProperties": False,
        },
        output_type="RecurringPaymentStatus[]",
    )
    allowed_arguments = ("year", "month")

    def _execute(self, *, actor, family, arguments):
        year, month = validate_period(arguments)
        items = BudgetService(
            family=family,
            year=year,
            month=month,
            materialize=False,
        ).get_recurring_summary()
        return {
            "period": PeriodDTO.create(year=year, month=month).__dict__,
            "currency": settings.DEFAULT_CURRENCY,
            "items": [RecurringPaymentStatusDTO.from_budget_item(item).to_dict() for item in items],
            "count": len(items),
        }
