from decimal import Decimal

from django.conf import settings

from core.assistant.deterministic.alerts import AlertEvaluator
from core.assistant.deterministic.normalizer import current_local_date
from core.assistant.deterministic.summaries import (
    ToolExecutionCache,
    build_category_chart,
    build_detail_actions,
    build_metric_block,
    build_payer_chart,
    build_pending_table,
    money_metric,
    pending_recurring_items,
    percentage_metric,
)
from core.assistant.visual_contract.builders import build_summary_card
from core.assistant.visual_contract.response import AssistantVisualResponse


class InitialResponseBuilder:
    def __init__(self, *, actor, family, request_id, tool_cache=None):
        self.cache = tool_cache or ToolExecutionCache(actor=actor, family=family)
        self.request_id = request_id
        self.alerts = AlertEvaluator(currency=settings.DEFAULT_CURRENCY)

    def build(self, *, intent, year, month):
        handlers = {
            "monthly_summary": self.monthly_summary,
            "monthly_spending": self.monthly_spending,
            "monthly_cash_balance": self.monthly_cash_balance,
            "pending_payments": self.pending_payments,
            "category_spending": self.category_spending,
            "payer_spending": self.payer_spending,
        }
        return handlers[intent](year=year, month=month)

    def _snapshots(self, *, year, month):
        budget = self.cache.execute("get_monthly_budget", year=year, month=month)
        cash = self.cache.execute("get_monthly_cash_summary", year=year, month=month)
        return budget, cash

    def _evaluated_alerts(self, *, budget, cash):
        today = current_local_date()
        future = (budget["period"]["year"], budget["period"]["month"]) > (today.year, today.month)
        return self.alerts.evaluate(budget=budget, cash=cash, period_is_future=future)

    def monthly_summary(self, *, year, month):
        budget, cash = self._snapshots(year=year, month=month)
        evaluated = self._evaluated_alerts(budget=budget, cash=cash)
        headline, description, status = self._summary_conclusion(budget=budget, cash=cash, evaluated=evaluated)
        blocks = [
            build_summary_card(
                id="summary_1",
                title=budget["period"]["label"],
                headline=headline,
                description=description,
                status=status,
            ),
            build_metric_block([
                money_metric(key="actual_income", label="Ingresos", value=cash["income"]["actual"], help_text="Ingresos reales registrados."),
                money_metric(key="total_spent", label="Gastado", value=cash["outflows"]["total"], help_text="Salidas reales registradas."),
                money_metric(
                    key="cash_balance",
                    label="Balance",
                    value=cash["cash_balance"],
                    status="negative" if Decimal(cash["cash_balance"]) < 0 else "neutral",
                    help_text="Ingresos reales menos gastos reales.",
                ),
                money_metric(key="planned_pending", label="Pendiente", value=budget["planned"]["pending"], help_text="Obligaciones planificadas pendientes."),
            ]),
        ]
        blocks.extend(item.block for item in evaluated[:2])
        blocks.append(build_detail_actions(
            detail_intent="monthly_summary_detail",
            period=budget["period"],
            navigate_target="/",
            hidden_alerts=len(evaluated) > 2,
        ))
        return AssistantVisualResponse(
            intent="monthly_summary",
            summary=headline,
            blocks=blocks,
            period=budget["period"],
            has_more=True,
            request_id=self.request_id,
        ).to_dict()

    def monthly_spending(self, *, year, month):
        budget, cash = self._snapshots(year=year, month=month)
        spent = Decimal(cash["outflows"]["total"])
        evaluated = self._evaluated_alerts(budget=budget, cash=cash)
        headline = f"Habéis gastado {cash['outflows']['total']} {cash['currency']} este mes"
        status = "neutral" if spent == 0 else ("negative" if Decimal(cash["cash_balance"]) < 0 else "attention")
        blocks = [
            build_summary_card(
                id="summary_1",
                title=cash["period"]["label"],
                headline=headline,
                description="El total incluye gastos planificados y no planificados registrados.",
                status=status,
            ),
            build_metric_block([
                money_metric(key="total_spent", label="Gasto total", value=cash["outflows"]["total"]),
                money_metric(key="planned_spent", label="Planificado pagado", value=cash["outflows"]["planned"]),
                money_metric(key="unplanned_spent", label="No planificado", value=cash["outflows"]["unplanned"]),
                percentage_metric(key="percentage_used", label="Ejecución", value=budget["budget"]["percentage_used"]),
            ]),
        ]
        blocks.extend(item.block for item in evaluated[:2] if item.code in {"expenses_over_income", "budget_near_limit", "budget_exceeded"})
        blocks.append(build_detail_actions(
            detail_intent="monthly_expenses_detail",
            period=cash["period"],
            navigate_target="/expenses",
        ))
        return AssistantVisualResponse(
            intent="monthly_spending",
            summary=headline,
            blocks=blocks,
            period=cash["period"],
            has_more=True,
            request_id=self.request_id,
        ).to_dict()

    def monthly_cash_balance(self, *, year, month):
        budget, cash = self._snapshots(year=year, month=month)
        balance = Decimal(cash["cash_balance"])
        if balance < 0:
            headline = "Tus gastos superan tus ingresos"
            status = "critical"
        elif Decimal(cash["income"]["actual"]) == 0:
            headline = "No hay ingresos registrados en este periodo"
            status = "neutral"
        else:
            headline = "El balance de caja del mes es positivo"
            status = "positive"
        evaluated = self._evaluated_alerts(budget=budget, cash=cash)
        blocks = [
            build_summary_card(
                id="summary_1",
                title=cash["period"]["label"],
                headline=headline,
                description="El balance usa únicamente ingresos y gastos reales registrados.",
                status=status,
            ),
            build_metric_block([
                money_metric(key="actual_income", label="Ingresos", value=cash["income"]["actual"]),
                money_metric(key="total_spent", label="Gastos", value=cash["outflows"]["total"]),
                money_metric(key="cash_balance", label="Balance", value=cash["cash_balance"], status="negative" if balance < 0 else "neutral"),
            ]),
        ]
        blocks.extend(item.block for item in evaluated[:2])
        blocks.append(build_detail_actions(
            detail_intent="monthly_summary_detail",
            period=cash["period"],
            navigate_target="/dashboard",
            hidden_alerts=len(evaluated) > 2,
        ))
        return AssistantVisualResponse(
            intent="monthly_cash_balance",
            summary=headline,
            blocks=blocks,
            period=cash["period"],
            has_more=True,
            request_id=self.request_id,
        ).to_dict()

    def pending_payments(self, *, year, month):
        budget = self.cache.execute("get_monthly_budget", year=year, month=month)
        recurring = self.cache.execute("get_recurring_payment_status", year=year, month=month)
        pending_items = pending_recurring_items(recurring)
        fixed_pending = sum(Decimal(item["pending_amount"]) for item in pending_items)
        total_pending = Decimal(budget["planned"]["pending"])
        if total_pending == 0:
            headline, status = "No hay pagos planificados pendientes", "positive"
        elif pending_items:
            headline, status = f"Quedan {len(pending_items)} pagos fijos pendientes", "attention"
        else:
            headline, status = "Quedan obligaciones planificadas pendientes", "attention"
        blocks = [
            build_summary_card(
                id="summary_1",
                title=budget["period"]["label"],
                headline=headline,
                description="El pendiente refleja estados y movimientos registrados en backend.",
                status=status,
            ),
            build_metric_block([
                money_metric(key="planned_pending", label="Pendiente total", value=budget["planned"]["pending"]),
                money_metric(key="fixed_pending", label="Pagos fijos", value=str(fixed_pending.quantize(Decimal("0.01")))),
            ]),
        ]
        table = build_pending_table(recurring, limit=5)
        if table:
            blocks.append(table)
        if total_pending > 0:
            evaluated = self.alerts.evaluate(
                budget=budget,
                cash=self.cache.execute("get_monthly_cash_summary", year=year, month=month),
            )
            pending_alert = next((item.block for item in evaluated if item.code == "pending_payments"), None)
            if pending_alert:
                blocks.append(pending_alert)
        blocks.append(build_detail_actions(
            detail_intent="pending_payments_detail",
            period=budget["period"],
            navigate_target="/recurring",
        ))
        return AssistantVisualResponse(
            intent="pending_payments",
            summary=headline,
            blocks=blocks,
            period=budget["period"],
            has_more=len(pending_items) > 5,
            request_id=self.request_id,
        ).to_dict()

    def category_spending(self, *, year, month):
        categories = self.cache.execute("get_category_spending", year=year, month=month, limit=5)
        if categories["items"]:
            leader = categories["items"][0]
            headline = f"{leader['name']} es la categoría con mayor gasto"
            description = f"Acumula {leader['amount']} {categories['currency']} en el periodo."
            status = "neutral"
        else:
            headline = "No hay gastos por categoría en este periodo"
            description = "No existen movimientos registrados para comparar."
            status = "neutral"
        blocks = [build_summary_card(
            id="summary_1",
            title=categories["period"]["label"],
            headline=headline,
            description=description,
            status=status,
        )]
        chart = build_category_chart(categories, limit=5)
        if chart:
            blocks.append(chart)
        blocks.append(build_detail_actions(
            detail_intent="category_spending_detail",
            period=categories["period"],
            navigate_target="/categories",
        ))
        return AssistantVisualResponse(
            intent="category_spending",
            summary=headline,
            blocks=blocks,
            period=categories["period"],
            has_more=categories.get("has_more", False),
            request_id=self.request_id,
        ).to_dict()

    def payer_spending(self, *, year, month):
        payers = self.cache.execute("get_payer_spending", year=year, month=month)
        if payers["items"]:
            headline = "Este es el reparto del gasto registrado por persona"
            description = f"{payers['items'][0]['display_name']} tiene el importe más alto del periodo."
        else:
            headline = "No hay gastos asignados a personas en este periodo"
            description = "No existen movimientos registrados para comparar."
        blocks = [build_summary_card(
            id="summary_1",
            title=payers["period"]["label"],
            headline=headline,
            description=description,
            status="neutral",
        )]
        chart = build_payer_chart(payers, limit=10)
        if chart:
            blocks.append(chart)
        blocks.append(build_detail_actions(
            detail_intent="payer_spending_detail",
            period=payers["period"],
            navigate_target="/expenses",
        ))
        return AssistantVisualResponse(
            intent="payer_spending",
            summary=headline,
            blocks=blocks,
            period=payers["period"],
            has_more=payers.get("has_more", False),
            request_id=self.request_id,
        ).to_dict()

    @staticmethod
    def _summary_conclusion(*, budget, cash, evaluated):
        codes = {item.code for item in evaluated}
        income = Decimal(cash["income"]["actual"])
        spent = Decimal(cash["outflows"]["total"])
        pending = Decimal(budget["planned"]["pending"])
        if "expenses_over_income" in codes:
            return (
                "Tus gastos superan tus ingresos",
                "El balance real del mes es negativo según los movimientos registrados.",
                "critical",
            )
        if "budget_exceeded" in codes:
            return (
                "Habéis alcanzado el límite del presupuesto",
                "El gasto registrado alcanza o supera lo planificado para el mes.",
                "negative",
            )
        if income == 0 and spent == 0 and Decimal(budget["planned"]["total"]) == 0:
            return (
                "Aún no hay datos suficientes este mes",
                "No hay ingresos, gastos ni presupuesto registrados.",
                "neutral",
            )
        if income == 0:
            return (
                "Faltan ingresos registrados para completar la situación",
                "Hay actividad financiera, pero no consta ningún ingreso real en el periodo.",
                "attention",
            )
        if pending > 0:
            return (
                "Vais dentro del presupuesto, con pagos pendientes",
                "El gasto no supera el presupuesto, aunque quedan obligaciones por completar.",
                "attention",
            )
        return (
            "Vais dentro del presupuesto",
            "Los gastos registrados no superan los ingresos ni el presupuesto del periodo.",
            "positive",
        )
