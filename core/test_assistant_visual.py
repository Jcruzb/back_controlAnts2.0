from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from core.assistant.deterministic.alerts import AlertEvaluator
from core.assistant.deterministic.normalizer import (
    normalize_text,
    resolve_period,
)
from core.assistant.deterministic.router import DeterministicIntentRouter
from core.assistant.errors import (
    AmbiguousPeriodError,
    InvalidActionError,
    InvalidChartError,
    InvalidTableError,
    InvalidVisualBlockError,
    TooManyAlertsError,
    TooManyBlocksError,
    UnsupportedBlockTypeError,
)
from core.assistant.intents import INTENT_REGISTRY
from core.assistant.services import AssistantApplicationService
from core.assistant.visual_contract.actions import build_action, validate_actions
from core.assistant.visual_contract.builders import (
    build_action_group,
    build_alert,
    build_bar_chart,
    build_line_chart,
    build_metric_grid,
    build_question,
    build_recommendation,
    build_simple_table,
    build_summary_card,
)
from core.assistant.visual_contract.enums import BLOCK_VERSION, SCHEMA_VERSION
from core.assistant.visual_contract.formatting import build_period
from core.assistant.visual_contract.registry import BLOCK_REGISTRY, validate_block
from core.assistant.visual_contract.response import AssistantVisualResponse
from core.models import (
    Category,
    Expense,
    Income,
    Month,
    PlannedExpenseOccurrence,
    RecurringPayment,
    RecurringPaymentOccurrence,
)


def valid_summary():
    return build_summary_card(
        id="summary_1",
        title="Julio de 2026",
        headline="Vais dentro del presupuesto",
        description="Los datos registrados no superan los límites del mes.",
        status="positive",
    )


def valid_metrics():
    return build_metric_grid(
        id="metrics_1",
        items=[
            {
                "key": "actual_income",
                "label": "Ingresos",
                "value": "1000.00",
                "formatted_value": "1.000,00 €",
                "status": "neutral",
            },
            {
                "key": "total_spent",
                "label": "Gastado",
                "value": "500.00",
                "formatted_value": "500,00 €",
                "trend": {
                    "direction": "up",
                    "value": "12.50",
                    "formatted_value": "12,50 %",
                    "comparison_label": "respecto al mes anterior",
                    "meaning": "negative",
                },
            },
        ],
    )


def valid_alert():
    return build_alert(
        id="alert_pending",
        code="pending_payments",
        severity="warning",
        title="Quedan pagos pendientes",
        message="Hay importes planificados pendientes.",
        facts={"planned_pending": "100.00"},
    )


def valid_table():
    return build_simple_table(
        id="table_1",
        title="Gastos principales",
        columns=[
            {"key": "name", "label": "Gasto", "format": "text", "align": "left"},
            {"key": "amount", "label": "Importe", "format": "currency", "align": "right"},
        ],
        rows=[{"id": "expense_1", "name": "Alquiler", "amount": "900.00"}],
        limit=10,
        total_rows=1,
        has_more=False,
    )


def valid_bar_chart():
    return build_bar_chart(
        id="chart_1",
        title="Gastos por categoría",
        explanation="Vivienda concentra el mayor gasto.",
        x_axis={"key": "category", "label": "Categoría"},
        series=[{"key": "amount", "label": "Gastado", "format": "currency"}],
        data=[{"category": "Vivienda", "amount": "900.00"}],
    )


def valid_line_chart():
    return build_line_chart(
        id="chart_2",
        title="Evolución mensual",
        explanation="Los gastos aumentaron en el periodo mostrado.",
        x_axis={"key": "period", "label": "Mes"},
        series=[
            {"key": "expenses", "label": "Gastos", "format": "currency", "data_kind": "actual"}
        ],
        data=[
            {"period": "Junio de 2026", "expenses": "400.00"},
            {"period": "Julio de 2026", "expenses": "500.00"},
        ],
    )


def valid_recommendation():
    return build_recommendation(
        id="recommendation_1",
        level="not_recommended",
        headline="No se recomienda esta operación",
        explanation="El margen sería insuficiente.",
        reasons=[{"code": "low_margin", "text": "El margen mensual sería reducido."}],
        confidence="high",
    )


def valid_question():
    return build_question(
        id="question_1",
        question="¿De cuánto sería la cuota?",
        reason="Hace falta para calcular el impacto.",
        input={"type": "currency", "key": "monthly_payment", "required": True, "currency": "EUR"},
    )


def valid_action_group():
    return build_action_group(
        id="actions_1",
        layout="primary_secondary",
        actions=[build_action(
            id="view_more",
            type="fetch_detail",
            label="Ver más",
            intent="monthly_summary_detail",
            arguments={"year": 2026, "month": 7},
            style="primary",
        )],
    )


@override_settings(TIME_ZONE="Europe/Madrid")
class VisualContractTests(SimpleTestCase):
    def test_all_nine_blocks_validate_and_serialize(self):
        blocks = [
            valid_summary(),
            valid_metrics(),
            valid_alert(),
            valid_table(),
            valid_bar_chart(),
            valid_line_chart(),
            valid_recommendation(),
            valid_question(),
            valid_action_group(),
        ]

        self.assertEqual(len(blocks), 9)
        for block in blocks:
            self.assertIs(validate_block(block), block)

    def test_registry_is_closed_complete_and_versioned(self):
        self.assertIsInstance(BLOCK_REGISTRY, MappingProxyType)
        self.assertEqual(set(BLOCK_REGISTRY), {
            "summary_card", "metric_grid", "alert", "simple_table", "bar_chart",
            "line_chart", "recommendation", "question", "action_group",
        })
        self.assertTrue(all(block.version == BLOCK_VERSION for block in BLOCK_REGISTRY.values()))
        with self.assertRaises(TypeError):
            BLOCK_REGISTRY["html"] = object()
        with self.assertRaises(UnsupportedBlockTypeError):
            validate_block({"type": "html", "id": "bad_1"})

    def test_summary_validates_required_fields_enums_and_lengths(self):
        missing = valid_summary()
        missing.pop("headline")
        invalid_enum = valid_summary()
        invalid_enum["status"] = "great"
        too_long = valid_summary()
        too_long["headline"] = "x" * 91

        for payload in (missing, invalid_enum, too_long):
            with self.assertRaises(InvalidVisualBlockError):
                validate_block(payload)

    def test_metric_grid_rejects_float_duplicate_keys_and_limits(self):
        floating = valid_metrics()
        floating["items"][0]["value"] = 1.5
        duplicate = valid_metrics()
        duplicate["items"][1]["key"] = "actual_income"
        one_item = valid_metrics()
        one_item["items"] = one_item["items"][:1]
        five_items = valid_metrics()
        five_items["items"] = five_items["items"] * 3

        for payload in (floating, duplicate, one_item, five_items):
            with self.assertRaises(InvalidVisualBlockError):
                validate_block(payload)

    def test_table_rejects_float_too_many_columns_and_rows(self):
        floating = valid_table()
        floating["rows"][0]["amount"] = 900.0
        columns = valid_table()
        columns["columns"] = columns["columns"] * 3
        rows = valid_table()
        rows["rows"] = [deepcopy(rows["rows"][0]) for _ in range(11)]
        for index, row in enumerate(rows["rows"]):
            row["id"] = f"expense_{index}"
        rows["total_rows"] = 11
        empty_column = valid_table()
        empty_column["columns"].append(
            {"key": "payer", "label": "Pagador", "format": "text", "align": "left"}
        )
        empty_column["rows"][0]["payer"] = ""

        for payload in (floating, columns, rows, empty_column):
            with self.assertRaises(InvalidTableError):
                validate_block(payload)

    def test_charts_require_explanation_and_enforce_series_limits(self):
        bar = valid_bar_chart()
        bar.pop("explanation")
        line = valid_line_chart()
        line["series"] = line["series"] * 4
        unordered = valid_line_chart()
        unordered["data"].reverse()

        with self.assertRaises(InvalidChartError):
            validate_block(bar)
        with self.assertRaises(InvalidChartError):
            validate_block(line)
        with self.assertRaises(InvalidChartError):
            validate_block(unordered)

    def test_actions_enforce_allowlist_intents_limits_and_primary_count(self):
        with self.assertRaises(InvalidActionError):
            build_action(id="external", type="navigate", label="Fuera", target="https://evil.test", style="secondary")
        with self.assertRaises(InvalidActionError):
            build_action(id="unknown", type="fetch_detail", label="Detalle", intent="delete_expense", arguments={"year": 2026, "month": 7}, style="primary")
        with self.assertRaises(InvalidActionError):
            build_action(id="danger", type="navigate", label="Borrar", target="/expenses", style="danger")
        actions = [
            build_action(id=f"action_{index}", type="navigate", label="Abrir", target="/expenses", style="primary")
            for index in range(2)
        ]
        with self.assertRaises(InvalidActionError):
            validate_actions(actions)

    def test_response_envelope_orders_blocks_and_has_unique_ids(self):
        response = AssistantVisualResponse(
            intent="monthly_summary",
            summary="Vais dentro del presupuesto.",
            blocks=[valid_summary(), valid_metrics(), valid_action_group()],
            period=build_period(year=2026, month=7, timezone_name=settings.TIME_ZONE),
            request_id="req_test",
        ).to_dict()

        self.assertEqual(response["schema_version"], SCHEMA_VERSION)
        self.assertEqual(response["source"], "deterministic")
        self.assertEqual(response["intent"], "monthly_summary")
        self.assertTrue(response["response_id"].startswith("resp_"))
        self.assertEqual(response["meta"]["request_id"], "req_test")
        self.assertEqual(response["blocks"][0]["type"], "summary_card")

    def test_response_rejects_summary_position_duplicate_ids_and_global_limits(self):
        misplaced = AssistantVisualResponse(
            intent="monthly_summary",
            summary="Resumen",
            blocks=[valid_metrics(), valid_summary()],
        )
        duplicate = AssistantVisualResponse(
            intent="monthly_summary",
            summary="Resumen",
            blocks=[valid_summary(), valid_summary()],
        )
        too_many = AssistantVisualResponse(
            intent="monthly_summary",
            summary="Resumen",
            blocks=[valid_metrics() for _ in range(11)],
        )
        with self.assertRaises(InvalidVisualBlockError):
            misplaced.to_dict()
        with self.assertRaises(InvalidVisualBlockError):
            duplicate.to_dict()
        with self.assertRaises(TooManyBlocksError):
            too_many.to_dict()

    def test_deterministic_source_rejects_recommendation_question_and_three_alerts(self):
        for block in (valid_recommendation(), valid_question()):
            with self.assertRaises(InvalidVisualBlockError):
                AssistantVisualResponse(
                    intent="monthly_summary",
                    summary="Resumen",
                    blocks=[block],
                ).to_dict()
        alert_2 = valid_alert()
        alert_2["id"] = "alert_2"
        alert_2["code"] = "missing_income"
        alert_3 = valid_alert()
        alert_3["id"] = "alert_3"
        alert_3["code"] = "budget_exceeded"
        with self.assertRaises(TooManyAlertsError):
            AssistantVisualResponse(
                intent="monthly_summary",
                summary="Resumen",
                blocks=[valid_alert(), alert_2, alert_3],
            ).to_dict()

    def test_ai_source_can_validate_future_recommendation_and_question(self):
        recommendation = AssistantVisualResponse(
            intent="monthly_summary",
            summary="Evaluación futura",
            blocks=[valid_recommendation()],
            source="ai",
        ).to_dict()
        question = AssistantVisualResponse(
            intent="monthly_summary",
            summary="Falta información",
            blocks=[valid_question()],
            source="hybrid",
        ).to_dict()

        self.assertEqual(recommendation["source"], "ai")
        self.assertEqual(question["source"], "hybrid")


@override_settings(TIME_ZONE="Europe/Madrid")
class DeterministicRoutingTests(SimpleTestCase):
    def test_normalization_handles_accents_case_punctuation_and_spaces(self):
        self.assertEqual(
            normalize_text("  ¿CUÁNTO   hemos GASTADO? "),
            "cuanto hemos gastado",
        )

    def test_router_recognizes_frequent_equivalent_phrases(self):
        router = DeterministicIntentRouter()
        cases = {
            "¿Cómo vamos este mes?": "monthly_summary",
            "RESUMEN DEL MES!!!": "monthly_summary",
            "¿Cuánto hemos gastado?": "monthly_spending",
            "¿Qué pagos faltan?": "pending_payments",
            "¿En qué categoría gastamos más?": "category_spending",
            "¿Cuánto ha pagado cada persona?": "payer_spending",
            "¿Cuánto dinero nos queda?": "monthly_cash_balance",
        }
        for message, intent in cases.items():
            with self.subTest(message=message):
                match = router.match(message, reference_date=date(2026, 7, 15))
                self.assertEqual(match.intent, intent)
                self.assertEqual(match.confidence, "high")

    def test_period_resolves_explicit_current_previous_and_year_boundary(self):
        explicit = resolve_period("Estado de julio de 2026", reference_date=date(2026, 8, 1))
        current = resolve_period("este mes", reference_date=date(2026, 1, 5))
        previous = resolve_period("el mes anterior", reference_date=date(2026, 1, 5))
        december = resolve_period("diciembre", reference_date=date(2026, 7, 15))

        self.assertEqual((explicit.year, explicit.month), (2026, 7))
        self.assertEqual((current.year, current.month), (2026, 1))
        self.assertEqual((previous.year, previous.month), (2025, 12))
        self.assertEqual((december.year, december.month), (2026, 12))
        self.assertEqual(explicit.timezone, "Europe/Madrid")

    def test_period_rejects_real_ambiguity(self):
        for message in ("enero o febrero", "este mes y el mes pasado", "este mes de diciembre"):
            with self.subTest(message=message), self.assertRaises(AmbiguousPeriodError):
                resolve_period(message, reference_date=date(2026, 7, 15))

    def test_router_returns_medium_or_none_without_answering(self):
        router = DeterministicIntentRouter()

        self.assertEqual(router.match("presupuesto", reference_date=date(2026, 7, 15)).confidence, "medium")
        self.assertEqual(router.match("hola", reference_date=date(2026, 7, 15)).confidence, "none")

    def test_intent_registry_is_closed_and_contains_twelve_intents(self):
        self.assertIsInstance(INTENT_REGISTRY, MappingProxyType)
        self.assertEqual(len(INTENT_REGISTRY), 12)
        with self.assertRaises(TypeError):
            INTENT_REGISTRY["write_expense"] = {"detail": False}


@override_settings(
    TIME_ZONE="Europe/Madrid",
    ASSISTANT_BUDGET_NEAR_LIMIT_PERCENT="90.00",
)
class AlertEvaluatorTests(SimpleTestCase):
    def snapshots(self, *, income="1000.00", spent="500.00", planned="1000.00", pending="0.00", percentage="50.00"):
        period = {"year": 2026, "month": 7, "label": "Julio de 2026", "timezone": "Europe/Madrid"}
        budget = {
            "period": period,
            "planned": {"total": planned, "paid": spent, "pending": pending},
            "budget": {"percentage_used": percentage},
        }
        cash = {
            "period": period,
            "income": {"actual": income},
            "outflows": {"total": spent},
            "cash_balance": str((Decimal(income) - Decimal(spent)).quantize(Decimal("0.01"))),
        }
        return budget, cash

    def test_objective_alert_conditions_and_thresholds(self):
        evaluator = AlertEvaluator()
        budget, cash = self.snapshots(income="100.00", spent="150.00", planned="200.00", pending="50.00", percentage="95.00")
        codes = [item.code for item in evaluator.evaluate(budget=budget, cash=cash)]

        self.assertEqual(codes, ["expenses_over_income", "budget_near_limit", "pending_payments"])

    def test_budget_exceeded_at_100_and_missing_income_is_not_critical(self):
        evaluator = AlertEvaluator()
        budget, cash = self.snapshots(income="0.00", spent="100.00", planned="100.00", percentage="100.00")
        alerts = evaluator.evaluate(budget=budget, cash=cash)
        by_code = {item.code: item for item in alerts}

        self.assertEqual(by_code["budget_exceeded"].severity, "critical")
        self.assertEqual(by_code["missing_income"].severity, "info")

    def test_empty_period_uses_insufficient_data_without_missing_income(self):
        evaluator = AlertEvaluator()
        budget, cash = self.snapshots(income="0.00", spent="0.00", planned="0.00", percentage="0.00")
        codes = [item.code for item in evaluator.evaluate(budget=budget, cash=cash)]

        self.assertEqual(codes, ["insufficient_data"])


@override_settings(
    SECURE_SSL_REDIRECT=False,
    TIME_ZONE="Europe/Madrid",
    ASSISTANT_ENABLED=True,
    ASSISTANT_PROVIDER="mock",
    ASSISTANT_BUDGET_NEAR_LIMIT_PERCENT="90.00",
    DEFAULT_CURRENCY="EUR",
)
class DeterministicAssistantIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="visual-user",
            password="secret123",
            first_name="Ana",
            email="ana-sensitive@example.com",
        )
        self.family = self.user.profile.family
        self.category = Category.objects.create(
            family=self.family,
            name="Vivienda",
            icon="🏠",
        )
        self.month = Month.objects.create(family=self.family, year=2026, month=7)
        Income.objects.create(
            month=self.month,
            user=self.user,
            category=self.category,
            amount="100.00",
            date=date(2026, 7, 1),
        )
        self.recurring_paid = RecurringPayment.objects.create(
            family=self.family,
            category=self.category,
            payer=self.user,
            name="Alquiler",
            amount="100.00",
            due_day=1,
            start_date=date(2026, 1, 1),
        )
        self.recurring_pending = RecurringPayment.objects.create(
            family=self.family,
            category=self.category,
            payer=self.user,
            name="Seguro",
            amount="50.00",
            due_day=5,
            start_date=date(2026, 1, 1),
        )
        Expense.objects.create(
            month=self.month,
            user=self.user,
            payer=self.user,
            category=self.category,
            recurring_payment=self.recurring_paid,
            description="Alquiler",
            amount="150.00",
            date=date(2026, 7, 2),
        )
        self.client.force_authenticate(user=self.user)

    def test_known_query_uses_visual_contract_without_calling_provider(self):
        with patch("core.assistant.providers.mock.MockAssistantProvider.respond") as provider:
            response = self.client.post(
                "/api/assistant/messages/",
                {"message": "¿Cómo vamos en julio de 2026?"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["schema_version"], "1.0")
        self.assertEqual(response.data["source"], "deterministic")
        self.assertEqual(response.data["intent"], "monthly_summary")
        self.assertEqual(response.data["period"]["timezone"], "Europe/Madrid")
        self.assertEqual(response.data["blocks"][0]["type"], "summary_card")
        self.assertLessEqual(sum(block["type"] == "alert" for block in response.data["blocks"]), 2)
        provider.assert_not_called()

    def test_initial_summary_groups_hidden_alerts_behind_action(self):
        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "Resumen del mes de julio de 2026"},
            format="json",
        )

        alerts = [block for block in response.data["blocks"] if block["type"] == "alert"]
        action_group = next(block for block in response.data["blocks"] if block["type"] == "action_group")
        self.assertEqual([block["code"] for block in alerts], ["expenses_over_income", "budget_exceeded"])
        self.assertIn("view_other_alerts", [action["id"] for action in action_group["actions"]])

    def test_frequent_responses_use_real_data_and_no_pii(self):
        messages = {
            "¿Cuánto hemos gastado en julio de 2026?": "monthly_spending",
            "¿Qué pagos faltan en julio de 2026?": "pending_payments",
            "¿En qué categoría gastamos más en julio de 2026?": "category_spending",
            "¿Cuánto ha pagado cada persona en julio de 2026?": "payer_spending",
        }
        for message, intent in messages.items():
            with self.subTest(intent=intent):
                response = self.client.post("/api/assistant/messages/", {"message": message}, format="json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["intent"], intent)
                self.assertNotIn("sensitive@example.com", str(response.data))
                self.assertNotIn("payer_id", str(response.data))

    def test_detail_intent_returns_progressive_bounded_response(self):
        previous_month = Month.objects.create(family=self.family, year=2026, month=6)
        Income.objects.create(
            month=previous_month,
            user=self.user,
            category=self.category,
            amount="90.00",
            date=date(2026, 6, 1),
        )
        Expense.objects.create(
            month=previous_month,
            user=self.user,
            payer=self.user,
            category=self.category,
            amount="50.00",
            date=date(2026, 6, 2),
        )
        with patch("core.assistant.providers.mock.MockAssistantProvider.respond") as provider:
            response = self.client.post(
                "/api/assistant/messages/",
                {"intent": "monthly_summary_detail", "arguments": {"year": 2026, "month": 7}},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["intent"], "monthly_summary_detail")
        self.assertEqual(response.data["source"], "deterministic")
        self.assertLessEqual(len(response.data["blocks"]), 10)
        table = next(block for block in response.data["blocks"] if block["type"] == "simple_table")
        self.assertLessEqual(len(table["rows"]), 10)
        line_chart = next(block for block in response.data["blocks"] if block["type"] == "line_chart")
        self.assertTrue(line_chart["explanation"])
        provider.assert_not_called()

    def test_invalid_detail_intent_and_tenant_fields_are_rejected(self):
        invalid_intent = self.client.post(
            "/api/assistant/messages/",
            {"intent": "delete_expense", "arguments": {"year": 2026, "month": 7}},
            format="json",
        )
        tenant = self.client.post(
            "/api/assistant/messages/",
            {"intent": "monthly_summary_detail", "arguments": {"year": 2026, "month": 7}, "family_id": 999},
            format="json",
        )
        nested_tenant = self.client.post(
            "/api/assistant/messages/",
            {
                "intent": "monthly_summary_detail",
                "arguments": {"year": 2026, "month": 7, "user_id": self.user.id},
            },
            format="json",
        )

        self.assertEqual(invalid_intent.status_code, 400)
        self.assertEqual(invalid_intent.data["error"]["code"], "unsupported_intent")
        self.assertEqual(tenant.data["error"]["code"], "invalid_arguments")
        self.assertEqual(nested_tenant.data["error"]["code"], "invalid_period")

    def test_ambiguous_natural_period_returns_stable_error(self):
        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "Estado de enero o febrero"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "ambiguous_period")

    def test_unknown_query_uses_mock_routing_and_keeps_visual_contract(self):
        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-07", "allow_ai": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "hybrid")
        self.assertEqual(response.data["meta"]["provider"], "mock")
        self.assertEqual(response.data["schema_version"], "1.0")
        self.assertEqual(response.data["intent"], "monthly_summary")

    def test_family_isolation_in_visual_aggregates(self):
        other = User.objects.create_user(username="visual-other", password="secret123")
        other_category = Category.objects.create(family=other.profile.family, name="Ajena", icon="🔒")
        other_month = Month.objects.create(family=other.profile.family, year=2026, month=7)
        Expense.objects.create(
            month=other_month,
            user=other,
            payer=other,
            category=other_category,
            amount="9999.00",
            date=date(2026, 7, 1),
        )

        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "¿Cuánto hemos gastado en julio de 2026?"},
            format="json",
        )

        serialized = str(response.data)
        self.assertNotIn("9999.00", serialized)
        self.assertIn("150.00", serialized)

    def test_deterministic_queries_are_read_only_and_do_not_materialize(self):
        Month.objects.filter(family=self.family, year=2027, month=12).delete()
        before_expenses = Expense.objects.count()
        before_categories = Category.objects.count()

        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "Estado de diciembre de 2027"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Month.objects.filter(family=self.family, year=2027, month=12).exists())
        self.assertEqual(Expense.objects.count(), before_expenses)
        self.assertEqual(Category.objects.count(), before_categories)
        self.assertFalse(PlannedExpenseOccurrence.objects.filter(month__year=2027).exists())
        self.assertFalse(RecurringPaymentOccurrence.objects.filter(month__year=2027).exists())

    def test_application_service_lazily_avoids_provider_for_known_query(self):
        provider = type("Provider", (), {"name": "mock", "respond": lambda *args, **kwargs: self.fail("provider called")})()
        service = AssistantApplicationService(provider=provider)

        response = service.process(
            actor=self.user,
            family=self.family,
            message="¿Cómo vamos en julio de 2026?",
        )

        self.assertEqual(response["source"], "deterministic")
