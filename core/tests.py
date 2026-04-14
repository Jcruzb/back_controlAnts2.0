from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Category, Expense, Family, Month


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
        self.assertEqual(str(response.data["unplanned_total"]), "20")
