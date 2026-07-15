from decimal import Decimal
from copy import deepcopy

from django.conf import settings

from core.assistant.errors import error_from_payload
from core.assistant.registry import ToolRegistry
from core.assistant.visual_contract.actions import build_action
from core.assistant.visual_contract.builders import (
    build_action_group,
    build_bar_chart,
    build_metric_grid,
    build_simple_table,
)
from core.assistant.visual_contract.formatting import (
    format_currency,
    format_percentage,
)


class ToolExecutionCache:
    def __init__(self, *, actor, family, registry=None):
        self.actor = actor
        self.family = family
        self.registry = registry or ToolRegistry()
        self._cache = {}

    def execute(self, tool_name, **arguments):
        key = (tool_name, tuple(sorted(arguments.items())))
        if key not in self._cache:
            result = self.registry.get(tool_name).execute(
                actor=self.actor,
                family=self.family,
                arguments=arguments,
            )
            if not result.ok:
                raise error_from_payload(result.error)
            data = deepcopy(result.data)
            if isinstance(data.get("period"), dict):
                data["period"].setdefault("timezone", settings.TIME_ZONE)
            self._cache[key] = data
        return self._cache[key]


def money_metric(*, key, label, value, status="neutral", help_text=None, currency=None):
    currency = currency or settings.DEFAULT_CURRENCY
    item = {
        "key": key,
        "label": label,
        "value": value,
        "formatted_value": format_currency(value, currency),
        "status": status,
    }
    if help_text:
        item["help_text"] = help_text
    return item


def percentage_metric(*, key, label, value, status="neutral", help_text=None):
    item = {
        "key": key,
        "label": label,
        "value": value,
        "formatted_value": format_percentage(value),
        "status": status,
    }
    if help_text:
        item["help_text"] = help_text
    return item


def build_detail_actions(*, detail_intent, period, navigate_target, hidden_alerts=False):
    actions = [build_action(
        id="view_more",
        type="fetch_detail",
        label="Ver más",
        intent=detail_intent,
        arguments={"year": period["year"], "month": period["month"]},
        style="primary",
    )]
    actions.append(build_action(
        id="navigate_section",
        type="navigate",
        label="Abrir sección",
        target=navigate_target,
        style="secondary",
    ))
    if hidden_alerts:
        actions.append(build_action(
            id="view_other_alerts",
            type="fetch_detail",
            label="Ver otras alertas",
            intent="other_alerts_detail",
            arguments={"year": period["year"], "month": period["month"]},
            style="secondary",
        ))
    return build_action_group(
        id="actions_1",
        layout="primary_secondary",
        actions=actions,
    )


def build_expense_table(expenses, *, limit=10, title="Gastos principales"):
    items = expenses["items"][:limit]
    if not items:
        return None
    columns = [
        {"key": "name", "label": "Gasto", "format": "text", "align": "left"},
        {"key": "amount", "label": "Importe", "format": "currency", "align": "right"},
        {"key": "date", "label": "Fecha", "format": "date", "align": "right"},
    ]
    rows = [
        {
            "id": f"expense_{item['id']}",
            "name": item["name"],
            "amount": item["amount"],
            "date": item["date"],
            "formatted_amount": format_currency(item["amount"], settings.DEFAULT_CURRENCY),
        }
        for item in items
    ]
    return build_simple_table(
        id="table_expenses",
        title=title,
        description="Movimientos de mayor importe del periodo.",
        columns=columns,
        rows=rows,
        limit=limit,
        total_rows=expenses.get("total_count", expenses["count"]),
        has_more=expenses.get("has_more", False),
    )


def pending_recurring_items(recurring):
    return [item for item in recurring["items"] if Decimal(item["pending_amount"]) > 0]


def build_pending_table(recurring, *, limit=10):
    pending = pending_recurring_items(recurring)
    if not pending:
        return None
    rows = [
        {
            "id": f"recurring_{item['id']}",
            "name": item["name"],
            "planned": item["planned_amount"],
            "paid": item["paid_amount"],
            "pending": item["pending_amount"],
        }
        for item in pending[:limit]
    ]
    return build_simple_table(
        id="table_pending",
        title="Pagos fijos pendientes",
        description="Importes pendientes según movimientos y estados registrados.",
        columns=[
            {"key": "name", "label": "Pago", "format": "text", "align": "left"},
            {"key": "planned", "label": "Planificado", "format": "currency", "align": "right"},
            {"key": "paid", "label": "Pagado", "format": "currency", "align": "right"},
            {"key": "pending", "label": "Pendiente", "format": "currency", "align": "right"},
        ],
        rows=rows,
        limit=limit,
        total_rows=len(pending),
        has_more=len(pending) > limit,
    )


def build_category_chart(categories, *, limit=10):
    items = categories["items"][:limit]
    if not items:
        return None
    leader = items[0]["name"]
    return build_bar_chart(
        id="chart_categories",
        title="Gastos por categoría",
        explanation=f"{leader} es la categoría con mayor gasto del periodo.",
        x_axis={"key": "category", "label": "Categoría"},
        series=[{"key": "amount", "label": "Gastado", "format": "currency"}],
        data=[{"category": item["name"], "amount": item["amount"]} for item in items],
    )


def build_payer_chart(payers, *, limit=10):
    items = payers["items"][:limit]
    if not items:
        return None
    leader = items[0]["display_name"]
    return build_bar_chart(
        id="chart_payers",
        title="Gasto por persona",
        explanation=f"{leader} es quien tiene más gasto registrado en el periodo.",
        x_axis={"key": "payer", "label": "Persona"},
        series=[{"key": "amount", "label": "Pagado", "format": "currency"}],
        data=[{"payer": item["display_name"], "amount": item["amount"]} for item in items],
    )


def build_metric_block(items):
    return build_metric_grid(id="metrics_1", items=items)
