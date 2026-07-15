from datetime import date
from types import MappingProxyType
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from core.assistant.errors import UnsupportedRequestError, UnsupportedToolError
from core.assistant.providers.mock import MockAssistantProvider
from core.assistant.registry import TOOL_REGISTRY, ToolRegistry
from core.assistant.tools import (
    GetCategorySpendingTool,
    GetMonthlyBudgetTool,
    GetMonthlyCashSummaryTool,
    GetPayerSpendingTool,
    GetRecurringPaymentStatusTool,
    ListMonthlyExpensesTool,
)
from core.assistant.unsupported import UnsupportedRequestClassifier
from core.models import (
    Category,
    Expense,
    Income,
    Month,
    PlannedExpenseOccurrence,
    PlannedExpensePlan,
    PlannedExpenseVersion,
    RecurringPayment,
    RecurringPaymentOccurrence,
)


@override_settings(SECURE_SSL_REDIRECT=False, DEFAULT_CURRENCY="EUR")
class AssistantReadToolTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="assistant-admin",
            password="secret123",
            email="admin-sensitive@example.com",
            first_name="Ana",
        )
        self.family = self.user.profile.family
        self.user.profile.role = "admin"
        self.user.profile.save(update_fields=["role"])

        self.member = User.objects.create_user(
            username="assistant-member",
            password="secret123",
            email="member-sensitive@example.com",
            first_name="Luis",
        )
        self.member.profile.family = self.family
        self.member.profile.save(update_fields=["family"])

        self.foreign_user = User.objects.create_user(
            username="assistant-foreign",
            password="secret123",
        )
        self.foreign_family = self.foreign_user.profile.family
        self.category = Category.objects.create(
            family=self.family,
            name="Alimentación",
            icon="🛒",
        )
        self.foreign_category = Category.objects.create(
            family=self.foreign_family,
            name="Ajena",
            icon="🔒",
        )
        self.month = Month.objects.create(family=self.family, year=2026, month=9)
        self.plan = PlannedExpensePlan.objects.create(
            family=self.family,
            category=self.category,
            name="Compra mensual",
            plan_type="ONGOING",
            start_month=self.month,
            created_by=self.user,
        )
        PlannedExpenseVersion.objects.create(
            plan=self.plan,
            planned_amount="100.00",
            valid_from=self.month,
        )
        self.recurring = RecurringPayment.objects.create(
            family=self.family,
            category=self.category,
            payer=self.member,
            name="Seguro",
            amount="50.00",
            due_day=5,
            start_date=date(2026, 1, 1),
        )
        Income.objects.create(
            month=self.month,
            user=self.user,
            amount="200.00",
            category=self.category,
            date=date(2026, 9, 1),
        )
        self.planned_expense = Expense.objects.create(
            month=self.month,
            user=self.user,
            payer=self.user,
            category=self.category,
            planned_expense_plan=self.plan,
            amount="40.00",
            date=date(2026, 9, 10),
            description="Compra supermercado",
        )
        self.recurring_expense = Expense.objects.create(
            month=self.month,
            user=self.user,
            payer=self.member,
            category=self.category,
            recurring_payment=self.recurring,
            amount="10.00",
            date=date(2026, 9, 5),
            description="Seguro parcial",
        )
        self.unplanned_expense = Expense.objects.create(
            month=self.month,
            user=self.user,
            payer=self.user,
            category=self.category,
            amount="20.00",
            date=date(2026, 9, 12),
            description="Compra espontánea",
        )

    def execute(self, tool, **arguments):
        return tool.execute(
            actor=self.user,
            family=self.family,
            arguments=arguments,
        )

    def test_monthly_budget_dto_separates_paid_pending_and_variance(self):
        result = self.execute(GetMonthlyBudgetTool(), year=2026, month=9)

        self.assertTrue(result.ok)
        self.assertEqual(result.data["period"]["label"], "Septiembre de 2026")
        self.assertEqual(result.data["currency"], "EUR")
        self.assertEqual(result.data["planned"], {
            "total": "150.00",
            "paid": "50.00",
            "pending": "100.00",
        })
        self.assertEqual(result.data["unplanned"]["total"], "20.00")
        self.assertEqual(result.data["budget"]["variance"], "80.00")

    def test_monthly_cash_dto_uses_real_income_and_outflows(self):
        result = self.execute(GetMonthlyCashSummaryTool(), year=2026, month=9)

        self.assertTrue(result.ok)
        self.assertEqual(result.data["income"]["actual"], "200.00")
        self.assertEqual(result.data["outflows"], {
            "total": "70.00",
            "planned": "50.00",
            "unplanned": "20.00",
        })
        self.assertEqual(result.data["cash_balance"], "130.00")

    def test_monthly_cash_dto_preserves_negative_balance(self):
        Income.objects.all().delete()

        result = self.execute(GetMonthlyCashSummaryTool(), year=2026, month=9)

        self.assertTrue(result.ok)
        self.assertEqual(result.data["cash_balance"], "-70.00")

    def test_budget_and_recurring_tools_do_not_materialize_month_or_occurrences(self):
        Month.objects.filter(family=self.family, year=2027, month=2).delete()

        budget = self.execute(GetMonthlyBudgetTool(), year=2027, month=2)
        recurring = self.execute(GetRecurringPaymentStatusTool(), year=2027, month=2)

        self.assertTrue(budget.ok)
        self.assertTrue(recurring.ok)
        self.assertFalse(
            Month.objects.filter(family=self.family, year=2027, month=2).exists()
        )

    def test_assistant_tools_do_not_create_occurrences_for_existing_month(self):
        PlannedExpenseOccurrence.objects.all().delete()
        RecurringPaymentOccurrence.objects.all().delete()

        self.execute(GetMonthlyBudgetTool(), year=2026, month=9)
        self.execute(GetRecurringPaymentStatusTool(), year=2026, month=9)

        self.assertEqual(PlannedExpenseOccurrence.objects.count(), 0)
        self.assertEqual(RecurringPaymentOccurrence.objects.count(), 0)

    def test_expense_tool_is_bounded_ordered_and_minimizes_pii(self):
        with self.assertNumQueries(1):
            result = self.execute(
                ListMonthlyExpensesTool(),
                year=2026,
                month=9,
                ordering="-amount",
                limit=2,
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["count"], 2)
        self.assertTrue(result.data["has_more"])
        self.assertEqual([item["amount"] for item in result.data["items"]], ["40.00", "20.00"])
        serialized = str(result.data)
        self.assertNotIn("sensitive@example.com", serialized)
        self.assertNotIn("email", serialized)
        self.assertEqual(result.data["items"][0]["payer"], {"display_name": "Ana"})

    def test_expense_tool_filters_planned_category_and_payer(self):
        result = self.execute(
            ListMonthlyExpensesTool(),
            year=2026,
            month=9,
            category_id=self.category.id,
            payer_id=self.member.id,
            planned=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual([item["id"] for item in result.data["items"]], [self.recurring_expense.id])

    def test_expense_tool_rejects_foreign_category_and_payer(self):
        category_result = self.execute(
            ListMonthlyExpensesTool(),
            year=2026,
            month=9,
            category_id=self.foreign_category.id,
        )
        payer_result = self.execute(
            ListMonthlyExpensesTool(),
            year=2026,
            month=9,
            payer_id=self.foreign_user.id,
        )

        self.assertEqual(category_result.error["code"], "resource_not_found")
        self.assertEqual(payer_result.error["code"], "resource_not_found")

    def test_tools_reject_invalid_period_limit_and_tenant_arguments(self):
        invalid_month = self.execute(GetMonthlyBudgetTool(), year=2026, month=13)
        invalid_limit = self.execute(
            ListMonthlyExpensesTool(), year=2026, month=9, limit=101
        )
        tenant_override = GetMonthlyBudgetTool().execute(
            actor=self.user,
            family=self.family,
            arguments={"year": 2026, "month": 9, "user_id": self.foreign_user.id},
        )

        self.assertEqual(invalid_month.error["code"], "invalid_arguments")
        self.assertEqual(invalid_limit.error["code"], "invalid_arguments")
        self.assertEqual(tenant_override.error["code"], "invalid_arguments")

    def test_tools_return_empty_month_without_inventing_values(self):
        expenses = self.execute(ListMonthlyExpensesTool(), year=2027, month=1)
        categories = self.execute(GetCategorySpendingTool(), year=2027, month=1)
        payers = self.execute(GetPayerSpendingTool(), year=2027, month=1)

        self.assertEqual(expenses.data["items"], [])
        self.assertEqual(categories.data["total"], "0.00")
        self.assertEqual(categories.data["items"], [])
        self.assertEqual(payers.data["total"], "0.00")
        self.assertEqual(payers.data["items"], [])

    def test_recurring_tool_uses_canonical_month_status_without_pii(self):
        result = self.execute(GetRecurringPaymentStatusTool(), year=2026, month=9)

        self.assertTrue(result.ok)
        self.assertEqual(result.data["count"], 1)
        item = result.data["items"][0]
        self.assertEqual(item["paid_amount"], "10.00")
        self.assertEqual(item["pending_amount"], "40.00")
        self.assertEqual(item["difference_amount"], "40.00")
        self.assertEqual(item["payment_status"], "partially_paid")
        self.assertEqual(item["payer"], {"display_name": "Luis"})
        self.assertNotIn("email", str(item))

    def test_category_and_payer_spending_are_backend_aggregates(self):
        with self.assertNumQueries(2):
            categories = self.execute(GetCategorySpendingTool(), year=2026, month=9)
        with self.assertNumQueries(2):
            payers = self.execute(GetPayerSpendingTool(), year=2026, month=9)

        self.assertEqual(categories.data["total"], "70.00")
        self.assertEqual(categories.data["items"][0]["amount"], "70.00")
        self.assertEqual(categories.data["items"][0]["count"], 3)
        payer_amounts = {
            item["display_name"]: item["amount"] for item in payers.data["items"]
        }
        self.assertEqual(payer_amounts, {"Ana": "60.00", "Luis": "10.00"})
        self.assertNotIn("sensitive@example.com", str(payers.data))

    def test_tool_reports_service_error_without_stack_trace(self):
        with patch(
            "core.assistant.tools.budget.BudgetService.build_budget",
            side_effect=RuntimeError("database details must not escape"),
        ):
            result = self.execute(GetMonthlyBudgetTool(), year=2026, month=9)

        self.assertFalse(result.ok)
        self.assertEqual(result.error["code"], "tool_execution_failed")
        self.assertNotIn("database details", str(result.error))

    def test_user_without_profile_is_denied(self):
        orphan = User.objects.create_user(username="orphan", password="secret123")
        orphan_family = orphan.profile.family
        orphan.profile.delete()
        orphan = User.objects.get(pk=orphan.pk)

        result = GetMonthlyBudgetTool().execute(
            actor=orphan,
            family=orphan_family,
            arguments={"year": 2026, "month": 9},
        )

        self.assertEqual(result.error["code"], "permission_denied")


class AssistantRegistryAndProviderTests(SimpleTestCase):
    def test_registry_is_static_read_only_and_complete(self):
        registry = ToolRegistry()

        self.assertIsInstance(TOOL_REGISTRY, MappingProxyType)
        self.assertEqual(
            registry.names(),
            (
                "get_monthly_budget",
                "get_monthly_cash_summary",
                "list_monthly_expenses",
                "get_recurring_payment_status",
                "get_category_spending",
                "get_payer_spending",
            ),
        )
        for metadata in registry.metadata():
            self.assertEqual(metadata["mode"], "read")
            self.assertFalse(metadata["requires_confirmation"])
            self.assertEqual(metadata["version"], "1.0")
        with self.assertRaises(TypeError):
            TOOL_REGISTRY["write_tool"] = object()
        with self.assertRaises(UnsupportedToolError):
            registry.get("write_tool")

    def test_mock_provider_selects_tools_deterministically(self):
        provider = MockAssistantProvider()
        metadata = ToolRegistry().metadata()
        expected = {
            "budget": ("get_monthly_budget", {}),
            "cash": ("get_monthly_cash_summary", {}),
            "expenses": ("list_monthly_expenses", {"ordering": "-amount", "limit": 20}),
            "recurring": ("get_recurring_payment_status", {}),
            "categories": ("get_category_spending", {"limit": 10}),
            "payers": ("get_payer_spending", {}),
        }

        for command, (tool_name, extra_arguments) in expected.items():
            with self.subTest(command=command):
                decision = provider.respond(
                    messages=[{"role": "user", "content": f"{command}:2026-09"}],
                    available_tools=metadata,
                    context={},
                )
                self.assertEqual(decision.tool_name, tool_name)
                self.assertEqual(
                    decision.arguments,
                    {"year": 2026, "month": 9, **extra_arguments},
                )

    def test_mock_provider_rejects_unsupported_or_write_requests(self):
        provider = MockAssistantProvider()
        metadata = ToolRegistry().metadata()

        for message in ("hola", "delete_expense:2026-09"):
            with self.subTest(message=message), self.assertRaises(UnsupportedRequestError):
                provider.respond(
                    messages=[{"role": "user", "content": message}],
                    available_tools=metadata,
                    context={},
                )

    def test_unsupported_classifier_uses_minimal_categories(self):
        record = UnsupportedRequestClassifier().classify(
            error_code="unsupported_tool",
            provider="mock",
            request_id="request-1",
            tool_name=None,
        )

        self.assertEqual(record.category, "missing_endpoint")
        self.assertNotIn("message", record.to_dict())


@override_settings(
    SECURE_SSL_REDIRECT=False,
    ASSISTANT_ENABLED=True,
    ASSISTANT_PROVIDER="mock",
    ASSISTANT_MAX_MESSAGE_LENGTH=200,
    DEFAULT_CURRENCY="EUR",
)
class AssistantEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="endpoint-user", password="secret123")
        self.family = self.user.profile.family
        self.category = Category.objects.create(
            family=self.family,
            name="General",
            icon="📦",
        )
        self.month = Month.objects.create(family=self.family, year=2026, month=9)
        self.client.force_authenticate(user=self.user)

    def test_endpoint_requires_authentication(self):
        client = APIClient()

        response = client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-09"},
            format="json",
        )

        self.assertIn(response.status_code, (401, 403))

    @override_settings(ASSISTANT_ENABLED=False)
    def test_endpoint_is_disabled_by_default_flag(self):
        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-09"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"]["code"], "assistant_disabled")

    def test_endpoint_executes_mock_tool_with_stable_contract(self):
        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-09", "conversation_id": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider"], "mock")
        self.assertEqual(response.data["period"]["label"], "Septiembre de 2026")
        self.assertEqual(response.data["tool_calls"], [
            {"name": "get_monthly_budget", "status": "success"}
        ])
        self.assertIn("request_id", response.data)
        self.assertEqual(response.data["data"]["planned"]["total"], "0.00")

    def test_endpoint_preserves_family_isolation(self):
        other = User.objects.create_user(username="other-endpoint", password="secret123")
        other_category = Category.objects.create(
            family=other.profile.family,
            name="Ajena",
            icon="🔒",
        )
        other_month = Month.objects.create(
            family=other.profile.family,
            year=2026,
            month=9,
        )
        Expense.objects.create(
            month=other_month,
            user=other,
            payer=other,
            category=other_category,
            amount="999.00",
            date=date(2026, 9, 1),
        )

        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "cash:2026-09"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["outflows"]["total"], "0.00")

    def test_endpoint_returns_typed_input_and_provider_errors(self):
        invalid_month = self.client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-13"},
            format="json",
        )
        unsupported = self.client.post(
            "/api/assistant/messages/",
            {"message": "hola"},
            format="json",
        )

        self.assertEqual(invalid_month.status_code, 400)
        self.assertEqual(invalid_month.data["error"]["code"], "invalid_arguments")
        self.assertEqual(unsupported.status_code, 400)
        self.assertEqual(unsupported.data["error"]["code"], "unsupported_request")

    def test_endpoint_rejects_long_messages_tenant_fields_and_write_attempts(self):
        long_message = self.client.post(
            "/api/assistant/messages/",
            {"message": "x" * 201},
            format="json",
        )
        tenant_field = self.client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-09", "user_id": 999},
            format="json",
        )
        write_attempt = self.client.post(
            "/api/assistant/messages/",
            {"message": "delete_expense:2026-09"},
            format="json",
        )

        self.assertEqual(long_message.data["error"]["code"], "invalid_arguments")
        self.assertEqual(tenant_field.data["error"]["code"], "invalid_arguments")
        self.assertEqual(write_attempt.data["error"]["code"], "unsupported_request")

    @override_settings(ASSISTANT_PROVIDER="openai")
    def test_endpoint_rejects_unconfigured_real_provider(self):
        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-09"},
            format="json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["error"]["code"], "provider_unavailable")

    def test_session_authentication_enforces_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        csrf_response = client.get("/api/csrf/")
        token = csrf_response.cookies["csrftoken"].value

        rejected = client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-09"},
            format="json",
        )
        accepted = client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-09"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(accepted.status_code, 200)

    def test_endpoint_denies_user_without_profile(self):
        self.user.profile.delete()
        orphan = User.objects.get(pk=self.user.pk)
        self.client.force_authenticate(user=orphan)

        response = self.client.post(
            "/api/assistant/messages/",
            {"message": "budget:2026-09"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "permission_denied")
