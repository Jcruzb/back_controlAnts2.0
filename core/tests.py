from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient

from core.models import (
    Category,
    Expense,
    Family,
    Month,
    PlannedExpense,
    PlannedExpensePlan,
    PlannedExpenseVersion,
    RecurringPayment,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class MultiTenantSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.family_a = Family.objects.create(name="Familia A")
        self.family_b = Family.objects.create(name="Familia B")

        self.user_a = User.objects.create_user(username="alice", password="secret123")
        self.user_b = User.objects.create_user(username="bob", password="secret123")

        self.user_a.profile.family = self.family_a
        self.user_a.profile.role = "admin"
        self.user_a.profile.save(update_fields=["family", "role"])

        self.user_b.profile.family = self.family_b
        self.user_b.profile.role = "admin"
        self.user_b.profile.save(update_fields=["family", "role"])

        self.month_a = Month.objects.create(family=self.family_a, year=2026, month=4)
        self.month_b = Month.objects.create(family=self.family_b, year=2026, month=4)

        self.category_a = Category.objects.create(
            family=self.family_a,
            name="Comida",
            icon="food",
        )
        self.category_b = Category.objects.create(
            family=self.family_b,
            name="Privada",
            icon="lock",
        )

    def test_register_creates_isolated_family(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "carol",
                "password": "strongPass123",
                "family_name": "Familia Carol",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="carol")
        self.assertEqual(user.profile.family.name, "Familia Carol")
        self.assertEqual(user.profile.role, "admin")
        self.assertNotEqual(user.profile.family_id, self.family_a.id)
        self.assertNotEqual(user.profile.family_id, self.family_b.id)

    def test_expense_rejects_foreign_category(self):
        self.client.force_authenticate(user=self.user_a)

        response = self.client.post(
            "/api/expenses/",
            {
                "description": "Intento cruzado",
                "amount": "42.00",
                "category": self.category_b.id,
                "date": "2026-04-10",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.data)

    def test_recurring_payment_rejects_foreign_category(self):
        self.client.force_authenticate(user=self.user_a)

        response = self.client.post(
            "/api/recurring-payments/",
            {
                "name": "Netflix de otra familia",
                "amount": "15.99",
                "due_day": 5,
                "category": self.category_b.id,
                "start_date": "2026-04-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("category", response.data)

    def test_budget_only_uses_current_family_expenses(self):
        Expense.objects.create(
            month=self.month_a,
            user=self.user_a,
            amount="20.00",
            category=self.category_a,
            date=date(2026, 4, 10),
            description="Familia A",
        )
        Expense.objects.create(
            month=self.month_b,
            user=self.user_b,
            amount="999.00",
            category=self.category_b,
            date=date(2026, 4, 10),
            description="Familia B",
        )

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/api/budget/?year=2026&month=4")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["unplanned_total"]), "20.00")

    def test_budget_includes_consistent_category_fields_in_recurring_and_planned(self):
        recurring = RecurringPayment.objects.create(
            family=self.family_a,
            category=self.category_a,
            name="Internet",
            amount="50.00",
            due_day=10,
            start_date=date(2026, 1, 1),
            active=True,
        )
        Expense.objects.create(
            month=self.month_a,
            user=self.user_a,
            amount="25.00",
            category=self.category_a,
            recurring_payment=recurring,
            date=date(2026, 4, 10),
            description="Internet abril",
        )

        planned_expense = PlannedExpense.objects.create(
            month=self.month_a,
            family=self.family_a,
            category=self.category_a,
            name="Compra mensual",
            planned_amount="100.00",
            created_by=self.user_a,
        )
        Expense.objects.create(
            month=self.month_a,
            user=self.user_a,
            amount="40.00",
            category=self.category_a,
            planned_expense=planned_expense,
            date=date(2026, 4, 12),
            description="Supermercado",
        )

        transport_category = Category.objects.create(
            family=self.family_a,
            name="Transporte",
            icon="bus",
        )
        planned_plan = PlannedExpensePlan.objects.create(
            family=self.family_a,
            category=transport_category,
            name="Abono transporte",
            plan_type="ONGOING",
            active=True,
            start_month=self.month_a,
            created_by=self.user_a,
        )
        PlannedExpenseVersion.objects.create(
            plan=planned_plan,
            planned_amount="30.00",
            valid_from=self.month_a,
        )

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/api/budget/?year=2026&month=4")

        self.assertEqual(response.status_code, 200)

        recurring_item = response.data["recurring"][0]
        self.assertEqual(recurring_item["category"], self.category_a.id)
        self.assertEqual(recurring_item["category_name"], self.category_a.name)
        self.assertEqual(recurring_item["category_detail"]["id"], self.category_a.id)
        self.assertEqual(recurring_item["category_detail"]["name"], self.category_a.name)

        planned_items = response.data["planned"]
        self.assertEqual(len(planned_items), 2)

        for item in planned_items:
            self.assertIn("category", item)
            self.assertIn("category_name", item)
            self.assertIn("category_detail", item)
            self.assertEqual(item["category"], item["category_detail"]["id"])
            self.assertEqual(item["category_name"], item["category_detail"]["name"])

    def test_recurring_payment_payments_endpoint_returns_recurring_with_payments(self):
        recurring = RecurringPayment.objects.create(
            family=self.family_a,
            category=self.category_a,
            name="Netflix",
            amount="15.99",
            due_day=5,
            start_date=date(2026, 1, 1),
            active=True,
        )
        newer_payment = Expense.objects.create(
            month=self.month_a,
            user=self.user_a,
            amount="15.99",
            category=self.category_a,
            recurring_payment=recurring,
            date=date(2026, 4, 5),
            description="Netflix abril",
            is_recurring=True,
        )
        older_month = Month.objects.create(family=self.family_a, year=2026, month=3)
        older_payment = Expense.objects.create(
            month=older_month,
            user=self.user_a,
            amount="15.99",
            category=self.category_a,
            recurring_payment=recurring,
            date=date(2026, 3, 5),
            description="Netflix marzo",
            is_recurring=True,
        )

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/recurring-payments/{recurring.id}/payments/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], recurring.id)
        self.assertEqual(response.data["name"], "Netflix")
        self.assertEqual(response.data["category"], self.category_a.id)
        self.assertEqual(len(response.data["payments"]), 2)
        self.assertEqual(response.data["payments"][0]["id"], newer_payment.id)
        self.assertEqual(response.data["payments"][1]["id"], older_payment.id)
        self.assertEqual(response.data["payments"][0]["recurring_payment"], recurring.id)
        self.assertTrue(response.data["payments"][0]["is_recurring"])

    def test_recurring_payment_payments_endpoint_is_scoped_by_family(self):
        recurring = RecurringPayment.objects.create(
            family=self.family_b,
            category=self.category_b,
            name="Privado",
            amount="20.00",
            due_day=1,
            start_date=date(2026, 1, 1),
            active=True,
        )

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/recurring-payments/{recurring.id}/payments/")

        self.assertEqual(response.status_code, 404)
