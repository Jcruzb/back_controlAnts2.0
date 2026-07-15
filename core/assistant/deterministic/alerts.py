from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

from core.assistant.visual_contract.builders import build_alert
from core.assistant.visual_contract.formatting import format_currency, format_percentage


SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class EvaluatedAlert:
    code: str
    severity: str
    priority: int
    block: dict


class AlertEvaluator:
    def __init__(self, *, currency="EUR"):
        self.currency = currency
        self.near_limit = Decimal(str(settings.ASSISTANT_BUDGET_NEAR_LIMIT_PERCENT))

    def evaluate(self, *, budget, cash, period_is_future=False):
        income = Decimal(cash["income"]["actual"])
        spent = Decimal(cash["outflows"]["total"])
        balance = Decimal(cash["cash_balance"])
        planned_total = Decimal(budget["planned"]["total"])
        pending = Decimal(budget["planned"]["pending"])
        percentage = Decimal(budget["budget"]["percentage_used"])
        alerts = []

        if income > 0 and spent > income:
            excess = spent - income
            alerts.append(self._alert(
                code="expenses_over_income",
                severity="critical",
                priority=10,
                title="Tus gastos superan tus ingresos",
                message=f"Este mes has gastado {format_currency(excess, self.currency)} más de lo ingresado.",
                facts={
                    "actual_income": str(income.quantize(Decimal("0.01"))),
                    "total_spent": str(spent.quantize(Decimal("0.01"))),
                    "difference": str(balance.quantize(Decimal("0.01"))),
                },
                action_intent="monthly_expenses_detail",
                action_label="Ver gastos",
                period=budget["period"],
            ))

        if planned_total > 0 and percentage >= 100:
            alerts.append(self._alert(
                code="budget_exceeded",
                severity="critical",
                priority=20,
                title="Has alcanzado el límite del presupuesto",
                message=f"La ejecución presupuestaria es del {format_percentage(percentage)}.",
                facts={
                    "total_planned": budget["planned"]["total"],
                    "total_spent": cash["outflows"]["total"],
                    "percentage_used": budget["budget"]["percentage_used"],
                },
                action_intent="monthly_expenses_detail",
                action_label="Ver gastos",
                period=budget["period"],
            ))
        elif planned_total > 0 and self.near_limit <= percentage < 100:
            alerts.append(self._alert(
                code="budget_near_limit",
                severity="warning",
                priority=30,
                title="Te acercas al límite del presupuesto",
                message=f"Ya se ha utilizado el {format_percentage(percentage)} del presupuesto mensual.",
                facts={"percentage_used": budget["budget"]["percentage_used"]},
                action_intent="monthly_expenses_detail",
                action_label="Ver gastos",
                period=budget["period"],
            ))

        if pending > 0:
            alerts.append(self._alert(
                code="pending_payments",
                severity="warning",
                priority=40,
                title="Quedan pagos planificados pendientes",
                message=f"El importe pendiente registrado es {format_currency(pending, self.currency)}.",
                facts={"planned_pending": budget["planned"]["pending"]},
                action_intent="pending_payments_detail",
                action_label="Ver pagos",
                period=budget["period"],
            ))

        has_activity = spent > 0 or planned_total > 0
        if income == 0 and has_activity and not period_is_future:
            alerts.append(self._alert(
                code="missing_income",
                severity="info",
                priority=50,
                title="No hay ingresos registrados",
                message="No consta ningún ingreso real en el periodo consultado.",
                facts={"actual_income": cash["income"]["actual"]},
                action_intent=None,
                action_label=None,
                period=budget["period"],
            ))
        elif income == 0 and spent == 0 and planned_total == 0:
            alerts.append(self._alert(
                code="insufficient_data",
                severity="info",
                priority=60,
                title="Todavía no hay datos suficientes",
                message="No hay ingresos, gastos ni presupuesto registrados para este periodo.",
                facts={},
                action_intent=None,
                action_label=None,
                period=budget["period"],
            ))

        unique = {item.code: item for item in alerts}
        return sorted(
            unique.values(),
            key=lambda item: (SEVERITY_ORDER[item.severity], item.priority, item.code),
        )

    def _alert(
        self,
        *,
        code,
        severity,
        priority,
        title,
        message,
        facts,
        action_intent,
        action_label,
        period,
    ):
        action = None
        if action_intent:
            action = {
                "type": "fetch_detail",
                "label": action_label,
                "intent": action_intent,
                "arguments": {"year": period["year"], "month": period["month"]},
            }
        block = build_alert(
            id=f"alert_{code}",
            code=code,
            severity=severity,
            title=title,
            message=message,
            facts=facts,
            action=action,
        ) if action else build_alert(
            id=f"alert_{code}",
            code=code,
            severity=severity,
            title=title,
            message=message,
            facts=facts,
        )
        return EvaluatedAlert(code=code, severity=severity, priority=priority, block=block)
