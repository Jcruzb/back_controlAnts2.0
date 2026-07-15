from types import MappingProxyType

from core.assistant.errors import UnsupportedToolError
from core.assistant.tools import (
    GetCategorySpendingTool,
    GetMonthlyBudgetTool,
    GetMonthlyCashSummaryTool,
    GetPayerSpendingTool,
    GetRecurringPaymentStatusTool,
    ListMonthlyExpensesTool,
)


_TOOL_REGISTRY = MappingProxyType(
    {
        "get_monthly_budget": GetMonthlyBudgetTool(),
        "get_monthly_cash_summary": GetMonthlyCashSummaryTool(),
        "list_monthly_expenses": ListMonthlyExpensesTool(),
        "get_recurring_payment_status": GetRecurringPaymentStatusTool(),
        "get_category_spending": GetCategorySpendingTool(),
        "get_payer_spending": GetPayerSpendingTool(),
    }
)


class ToolRegistry:
    def __init__(self):
        self._tools = _TOOL_REGISTRY

    def get(self, name):
        try:
            return self._tools[name]
        except KeyError:
            raise UnsupportedToolError()

    def metadata(self):
        return [tool.metadata.to_dict() for tool in self._tools.values()]

    def names(self):
        return tuple(self._tools.keys())


TOOL_REGISTRY = _TOOL_REGISTRY

