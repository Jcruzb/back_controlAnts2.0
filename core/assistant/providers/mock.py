import re

from core.assistant.errors import UnsupportedRequestError
from core.assistant.providers.base import ProviderDecision


COMMAND_PATTERN = re.compile(
    r"^(budget|cash|expenses|recurring|categories|payers):(\d{4})-(\d{2})$"
)


class MockAssistantProvider:
    name = "mock"

    COMMAND_TO_TOOL = {
        "budget": "get_monthly_budget",
        "cash": "get_monthly_cash_summary",
        "expenses": "list_monthly_expenses",
        "recurring": "get_recurring_payment_status",
        "categories": "get_category_spending",
        "payers": "get_payer_spending",
    }

    def respond(self, *, messages, available_tools, context):
        if not messages:
            raise UnsupportedRequestError()
        message = str(messages[-1].get("content", "")).strip()
        match = COMMAND_PATTERN.fullmatch(message)
        if match is None:
            raise UnsupportedRequestError(
                "Usa un comando de prueba como budget:2026-09."
            )

        command, year_value, month_value = match.groups()
        tool_name = self.COMMAND_TO_TOOL[command]
        available_names = {item["name"] for item in available_tools}
        if tool_name not in available_names:
            raise UnsupportedRequestError()

        arguments = {"year": int(year_value), "month": int(month_value)}
        if command == "expenses":
            arguments.update({"ordering": "-amount", "limit": 20})
        elif command == "categories":
            arguments["limit"] = 10

        return ProviderDecision(tool_name=tool_name, arguments=arguments)

