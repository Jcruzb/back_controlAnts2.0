from decimal import Decimal

from django.conf import settings

from core.assistant.deterministic.alerts import AlertEvaluator
from core.assistant.deterministic.normalizer import current_local_date, shift_month
from core.assistant.deterministic.summaries import (
    ToolExecutionCache,
    build_category_chart,
    build_expense_table,
    build_payer_chart,
    build_pending_table,
)
from core.assistant.visual_contract.actions import build_action
from core.assistant.visual_contract.builders import (
    build_action_group,
    build_line_chart,
    build_simple_table,
    build_summary_card,
)
from core.assistant.visual_contract.response import AssistantVisualResponse


class DetailResponseBuilder:
    def __init__(self, *, actor, family, request_id, tool_cache=None):
        self.cache = tool_cache or ToolExecutionCache(actor=actor, family=family)
        self.request_id = request_id
        self.alerts = AlertEvaluator(currency=settings.DEFAULT_CURRENCY)

    def build(self, *, intent, year, month):
        handlers = {
            "monthly_summary_detail": self.monthly_summary_detail,
            "monthly_expenses_detail": self.monthly_expenses_detail,
            "pending_payments_detail": self.pending_payments_detail,
            "category_spending_detail": self.category_spending_detail,
            "payer_spending_detail": self.payer_spending_detail,
            "other_alerts_detail": self.other_alerts_detail,
        }
        return handlers[intent](year=year, month=month)

    def monthly_summary_detail(self, *, year, month):
        budget = self.cache.execute("get_monthly_budget", year=year, month=month)
        cash = self.cache.execute("get_monthly_cash_summary", year=year, month=month)
        categories = self.cache.execute("get_category_spending", year=year, month=month, limit=10)
        expenses = self.cache.execute("list_monthly_expenses", year=year, month=month, ordering="-amount", limit=10)
        recurring = self.cache.execute("get_recurring_payment_status", year=year, month=month)
        blocks = [build_summary_card(
            id="summary_1",
            title=budget["period"]["label"],
            headline="Detalle financiero del periodo",
            description="Categorías, movimientos y pagos se muestran con datos registrados en ControlAnts.",
            status="neutral",
        )]
        for block in (
            build_category_chart(categories, limit=10),
            build_expense_table(expenses, limit=10),
            build_pending_table(recurring, limit=10),
            self._history_chart(year=year, month=month),
        ):
            if block:
                blocks.append(block)
        if len(blocks) == 1:
            evaluated = self.alerts.evaluate(
                budget=budget,
                cash=cash,
                period_is_future=self._is_future(year=year, month=month),
            )
            if evaluated:
                blocks.append(evaluated[0].block)
        blocks.append(self._navigation_group(target="/dashboard"))
        return AssistantVisualResponse(
            intent="monthly_summary_detail",
            summary="Detalle financiero del periodo.",
            blocks=blocks,
            period=budget["period"],
            has_more=expenses.get("has_more", False) or categories.get("has_more", False),
            request_id=self.request_id,
        ).to_dict()

    def monthly_expenses_detail(self, *, year, month):
        expenses = self.cache.execute("list_monthly_expenses", year=year, month=month, ordering="-amount", limit=10)
        table = build_expense_table(expenses, limit=10, title="Gastos del periodo")
        count = expenses["count"]
        headline = f"Se muestran {count} gastos registrados" if count else "No hay gastos registrados"
        blocks = [build_summary_card(
            id="summary_1",
            title=expenses["period"]["label"],
            headline=headline,
            description="Los movimientos están ordenados de mayor a menor importe.",
            status="neutral",
        )]
        if table:
            blocks.append(table)
        blocks.append(self._navigation_group(target="/expenses"))
        return AssistantVisualResponse(
            intent="monthly_expenses_detail",
            summary=headline,
            blocks=blocks,
            period=expenses["period"],
            has_more=expenses.get("has_more", False),
            request_id=self.request_id,
        ).to_dict()

    def pending_payments_detail(self, *, year, month):
        recurring = self.cache.execute("get_recurring_payment_status", year=year, month=month)
        table = build_pending_table(recurring, limit=10)
        pending_count = sum(1 for item in recurring["items"] if Decimal(item["pending_amount"]) > 0)
        headline = f"Hay {pending_count} pagos fijos pendientes" if pending_count else "No hay pagos fijos pendientes"
        blocks = [build_summary_card(
            id="summary_1",
            title=recurring["period"]["label"],
            headline=headline,
            description="El detalle usa estados mensuales y movimientos registrados.",
            status="attention" if pending_count else "positive",
        )]
        if table:
            blocks.append(table)
        blocks.append(self._navigation_group(target="/recurring"))
        return AssistantVisualResponse(
            intent="pending_payments_detail",
            summary=headline,
            blocks=blocks,
            period=recurring["period"],
            has_more=pending_count > 10,
            request_id=self.request_id,
        ).to_dict()

    def category_spending_detail(self, *, year, month):
        categories = self.cache.execute("get_category_spending", year=year, month=month, limit=10)
        chart = build_category_chart(categories, limit=10)
        headline = "Detalle del gasto por categoría" if chart else "No hay gasto por categoría"
        blocks = [build_summary_card(
            id="summary_1",
            title=categories["period"]["label"],
            headline=headline,
            description="Las categorías están ordenadas por gasto real registrado.",
            status="neutral",
        )]
        if chart:
            blocks.append(chart)
        blocks.append(self._navigation_group(target="/categories"))
        return AssistantVisualResponse(
            intent="category_spending_detail",
            summary=headline,
            blocks=blocks,
            period=categories["period"],
            has_more=categories.get("has_more", False),
            request_id=self.request_id,
        ).to_dict()

    def payer_spending_detail(self, *, year, month):
        payers = self.cache.execute("get_payer_spending", year=year, month=month)
        chart = build_payer_chart(payers, limit=10)
        headline = "Detalle del gasto por persona" if chart else "No hay gasto asignado a personas"
        blocks = [build_summary_card(
            id="summary_1",
            title=payers["period"]["label"],
            headline=headline,
            description="Solo se muestran nombres visibles e importes agregados.",
            status="neutral",
        )]
        if chart:
            blocks.append(chart)
        blocks.append(self._navigation_group(target="/expenses"))
        return AssistantVisualResponse(
            intent="payer_spending_detail",
            summary=headline,
            blocks=blocks,
            period=payers["period"],
            has_more=payers.get("has_more", False),
            request_id=self.request_id,
        ).to_dict()

    def other_alerts_detail(self, *, year, month):
        budget = self.cache.execute("get_monthly_budget", year=year, month=month)
        cash = self.cache.execute("get_monthly_cash_summary", year=year, month=month)
        evaluated = self.alerts.evaluate(
            budget=budget,
            cash=cash,
            period_is_future=self._is_future(year=year, month=month),
        )
        rows = [
            {
                "id": f"alert_row_{item.code}",
                "severity": item.severity,
                "title": item.block["title"],
                "message": item.block["message"],
            }
            for item in evaluated[:10]
        ]
        headline = f"Hay {len(evaluated)} alertas objetivas" if evaluated else "No hay alertas objetivas"
        blocks = [build_summary_card(
            id="summary_1",
            title=budget["period"]["label"],
            headline=headline,
            description="Las alertas se basan únicamente en reglas y datos registrados.",
            status="attention" if evaluated else "positive",
        )]
        if rows:
            blocks.append(build_simple_table(
                id="table_alerts",
                title="Alertas del periodo",
                columns=[
                    {"key": "severity", "label": "Nivel", "format": "status", "align": "left"},
                    {"key": "title", "label": "Alerta", "format": "text", "align": "left"},
                    {"key": "message", "label": "Detalle", "format": "text", "align": "left"},
                ],
                rows=rows,
                limit=10,
                total_rows=len(evaluated),
                has_more=len(evaluated) > 10,
            ))
        blocks.append(self._navigation_group(target="/dashboard"))
        return AssistantVisualResponse(
            intent="other_alerts_detail",
            summary=headline,
            blocks=blocks,
            period=budget["period"],
            has_more=len(evaluated) > 10,
            request_id=self.request_id,
        ).to_dict()

    def _history_chart(self, *, year, month):
        data = []
        active_periods = 0
        for offset in (-2, -1, 0):
            item_year, item_month = shift_month(year, month, offset)
            cash = self.cache.execute("get_monthly_cash_summary", year=item_year, month=item_month)
            if Decimal(cash["income"]["actual"]) != 0 or Decimal(cash["outflows"]["total"]) != 0:
                active_periods += 1
            data.append({
                "period": cash["period"]["label"],
                "income": cash["income"]["actual"],
                "expenses": cash["outflows"]["total"],
            })
        if active_periods < 2:
            return None
        first = Decimal(data[0]["expenses"])
        last = Decimal(data[-1]["expenses"])
        if last > first:
            explanation = "Los gastos registrados han aumentado respecto al inicio del periodo mostrado."
        elif last < first:
            explanation = "Los gastos registrados han disminuido respecto al inicio del periodo mostrado."
        else:
            explanation = "Los gastos registrados se mantienen estables entre el primer y el último mes."
        return build_line_chart(
            id="chart_history",
            title="Evolución mensual",
            explanation=explanation,
            x_axis={"key": "period", "label": "Mes"},
            series=[
                {"key": "income", "label": "Ingresos", "format": "currency", "data_kind": "actual"},
                {"key": "expenses", "label": "Gastos", "format": "currency", "data_kind": "actual"},
            ],
            data=data,
        )

    @staticmethod
    def _navigation_group(*, target):
        return build_action_group(
            id="actions_1",
            layout="inline",
            actions=[build_action(
                id="navigate_section",
                type="navigate",
                label="Abrir sección",
                target=target,
                style="secondary",
            )],
        )

    @staticmethod
    def _is_future(*, year, month):
        today = current_local_date()
        return (year, month) > (today.year, today.month)
