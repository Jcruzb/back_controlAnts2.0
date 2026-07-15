from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Category,
    Expense,
    Family,
    Income,
    IncomePlan,
    IncomePlanVersion,
    Month,
    PlannedExpense,
    PlannedExpenseOccurrence,
    PlannedExpensePlan,
    PlannedExpenseVersion,
    RecurringPayment,
    RecurringPaymentOccurrence,
)
from core.services.recurring_payment_service import (
    calculate_recurring_payment_amounts,
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
    def test_expense_accepts_family_payer_and_defaults_to_request_user(self):
        family_member = User.objects.create_user(username="ana", password="secret123")
        family_member.profile.family = self.family_a
        family_member.profile.save(update_fields=["family"])

        self.client.force_authenticate(user=self.user_a)

        with_payer = self.client.post(
            "/api/expenses/",
            {
                "description": "Compra familiar",
                "amount": "42.00",
                "category": self.category_a.id,
                "payer": family_member.id,
                "date": "2026-04-10",
            },
            format="json",
        )
        self.assertEqual(with_payer.status_code, 201)
        self.assertEqual(with_payer.data["payer"], family_member.id)
        self.assertEqual(with_payer.data["payer_detail"]["username"], "ana")

        without_payer = self.client.post(
            "/api/expenses/",
            {
                "description": "Sin pagador explicito",
                "amount": "20.00",
                "category": self.category_a.id,
                "date": "2026-04-11",
            },
            format="json",
        )
        self.assertEqual(without_payer.status_code, 201)
        self.assertEqual(without_payer.data["payer"], self.user_a.id)

    def test_expense_rejects_foreign_payer(self):
        self.client.force_authenticate(user=self.user_a)

        response = self.client.post(
            "/api/expenses/",
            {
                "description": "Pagador cruzado",
                "amount": "42.00",
                "category": self.category_a.id,
                "payer": self.user_b.id,
                "date": "2026-04-10",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("payer", response.data)

    def test_expenses_can_filter_by_payer(self):
        family_member = User.objects.create_user(username="ana", password="secret123")
        family_member.profile.family = self.family_a
        family_member.profile.save(update_fields=["family"])

        first = Expense.objects.create(
            month=self.month_a,
            user=self.user_a,
            payer=self.user_a,
            amount="20.00",
            category=self.category_a,
            date=date(2026, 4, 10),
            description="Pagado por Alice",
        )
        Expense.objects.create(
            month=self.month_a,
            user=self.user_a,
            payer=family_member,
            amount="30.00",
            category=self.category_a,
            date=date(2026, 4, 11),
            description="Pagado por Ana",
        )

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/expenses/?payer={self.user_a.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["results"]], [first.id])

    def test_family_members_endpoint_returns_only_current_family_users(self):
        family_member = User.objects.create_user(
            username="ana",
            password="secret123",
            first_name="Ana",
            last_name="Familia",
        )
        family_member.profile.family = self.family_a
        family_member.profile.save(update_fields=["family"])

        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/api/family/members/")

        self.assertEqual(response.status_code, 200)
        usernames = {item["username"] for item in response.data}
        self.assertEqual(usernames, {"alice", "ana"})
        self.assertNotIn("bob", usernames)

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

    def test_recurring_payment_rejects_foreign_payer(self):
        self.client.force_authenticate(user=self.user_a)

        response = self.client.post(
            "/api/recurring-payments/",
            {
                "name": "Pago de otra familia",
                "amount": "15.99",
                "due_day": 5,
                "category": self.category_a.id,
                "payer": self.user_b.id,
                "start_date": "2026-04-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("payer", response.data)

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

    def test_generate_recurring_expenses_inherits_recurring_payer(self):
        recurring = RecurringPayment.objects.create(
            family=self.family_a,
            category=self.category_a,
            payer=self.user_a,
            name="Internet",
            amount="50.00",
            due_day=5,
            start_date=date(timezone.now().year, timezone.now().month, 1),
            active=True,
        )

        self.client.force_authenticate(user=self.user_a)
        response = self.client.post("/api/recurring/generate/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["created"], 1)
        generated = Expense.objects.get(recurring_payment=recurring)
        self.assertEqual(generated.payer_id, self.user_a.id)

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


@override_settings(SECURE_SSL_REDIRECT=False)
class IncomePlanAdjustmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.family = Family.objects.create(name="Familia Sueldos")
        self.user = User.objects.create_user(username="salary-user", password="secret123")
        self.user.profile.family = self.family
        self.user.profile.role = "admin"
        self.user.profile.save(update_fields=["family", "role"])

        self.category = Category.objects.create(
            family=self.family,
            name="Salario",
            icon="salary",
        )
        self.months = {
            month: Month.objects.create(family=self.family, year=2026, month=month)
            for month in range(1, 13)
        }
        self.plan = IncomePlan.objects.create(
            family=self.family,
            category=self.category,
            name="Nomina",
            plan_type="ONGOING",
            due_day=28,
            active=True,
            start_month=self.months[1],
            created_by=self.user,
        )
        IncomePlanVersion.objects.create(
            plan=self.plan,
            planned_amount="1000.00",
            valid_from=self.months[1],
        )
        self.client.force_authenticate(user=self.user)

    def _planned_amount_for_month(self, month):
        response = self.client.get(f"/api/income-plans/month/?year=2026&month={month}")
        self.assertEqual(response.status_code, 200)
        result = next(
            item for item in response.data["results"]
            if item["plan_id"] == self.plan.id
        )
        return result["planned_amount"]

    def _adjust(self, month, amount):
        response = self.client.post(
            f"/api/income-plans/{self.plan.id}/adjust/?year=2026&month={month}",
            {
                "amount": amount,
                "description": f"Ajuste mes {month}",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        return response

    def _active_versions_for_month(self, month):
        month_obj = self.months[month]
        versions = IncomePlanVersion.objects.filter(plan=self.plan).select_related(
            "valid_from",
            "valid_to",
        )
        active = []
        for version in versions:
            starts_before_or_at = (
                version.valid_from.year,
                version.valid_from.month,
            ) <= (month_obj.year, month_obj.month)
            ends_after_or_at = (
                version.valid_to is None
                or (version.valid_to.year, version.valid_to.month) >= (month_obj.year, month_obj.month)
            )
            if starts_before_or_at and ends_after_or_at:
                active.append(version)
        return active

    def test_adjustment_applies_forward_from_selected_month(self):
        self.assertEqual(self._planned_amount_for_month(7), "1000.00")

        self._adjust(8, "1300.00")

        self.assertEqual(self._planned_amount_for_month(7), "1000.00")
        self.assertEqual(self._planned_amount_for_month(8), "1300.00")
        self.assertEqual(self._planned_amount_for_month(9), "1300.00")
        self.assertEqual(self._planned_amount_for_month(10), "1300.00")

    def test_second_later_adjustment_preserves_previous_range(self):
        self._adjust(8, "1300.00")
        self._adjust(11, "1500.00")

        self.assertEqual(self._planned_amount_for_month(10), "1300.00")
        self.assertEqual(self._planned_amount_for_month(11), "1500.00")
        self.assertEqual(self._planned_amount_for_month(12), "1500.00")

    def test_adjustments_do_not_leave_overlapping_active_versions(self):
        self._adjust(8, "1300.00")
        self._adjust(11, "1500.00")

        for month in range(1, 13):
            self.assertEqual(len(self._active_versions_for_month(month)), 1)

        versions = list(
            IncomePlanVersion.objects.filter(plan=self.plan)
            .select_related("valid_from", "valid_to")
            .order_by("valid_from__month")
        )
        self.assertEqual(len(versions), 3)
        self.assertEqual(versions[0].valid_from.month, 1)
        self.assertEqual(versions[0].valid_to.month, 7)
        self.assertEqual(versions[1].valid_from.month, 8)
        self.assertEqual(versions[1].valid_to.month, 10)
        self.assertEqual(versions[2].valid_from.month, 11)
        self.assertIsNone(versions[2].valid_to)

    def test_confirm_does_not_change_plan_versions(self):
        self._adjust(8, "1300.00")
        before_versions = list(
            IncomePlanVersion.objects.filter(plan=self.plan)
            .order_by("valid_from__month")
            .values_list("planned_amount", "valid_from__month", "valid_to__month")
        )

        response = self.client.post(
            f"/api/income-plans/{self.plan.id}/confirm/?year=2026&month=9",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        income = Income.objects.get(id=response.data["income_id"])
        self.assertEqual(str(income.amount), "1300.00")

        after_versions = list(
            IncomePlanVersion.objects.filter(plan=self.plan)
            .order_by("valid_from__month")
            .values_list("planned_amount", "valid_from__month", "valid_to__month")
        )
        self.assertEqual(after_versions, before_versions)
        self.assertEqual(self._planned_amount_for_month(10), "1300.00")


@override_settings(SECURE_SSL_REDIRECT=False)
class AuthSelfManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="alice",
            password="secret123",
            first_name="Alice",
            last_name="Liddell",
            email="alice@example.com",
        )

    def test_me_get_returns_current_user_payload(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["authenticated"])
        self.assertEqual(response.data["user"]["username"], "alice")
        self.assertEqual(response.data["user"]["first_name"], "Alice")
        self.assertEqual(response.data["user"]["last_name"], "Liddell")
        self.assertEqual(response.data["user"]["email"], "alice@example.com")
        self.assertEqual(response.data["profile"]["role"], "member")
        self.assertIn("family", response.data)

    def test_me_patch_updates_basic_user_fields(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            "/api/auth/me/",
            {
                "first_name": "Alicia",
                "last_name": "Wonderland",
                "email": "alicia@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Alicia")
        self.assertEqual(self.user.last_name, "Wonderland")
        self.assertEqual(self.user.email, "alicia@example.com")
        self.assertEqual(response.data["user"]["username"], "alice")
        self.assertEqual(response.data["user"]["first_name"], "Alicia")

    def test_change_password_succeeds_with_valid_current_password(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "secret123",
                "new_password": "newStrongPass123",
                "new_password_confirm": "newStrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newStrongPass123"))
        self.assertIsNotNone(
            authenticate(username="alice", password="newStrongPass123")
        )

    def test_change_password_rejects_incorrect_current_password(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "wrong-password",
                "new_password": "newStrongPass123",
                "new_password_confirm": "newStrongPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.data)

    def test_change_password_rejects_mismatched_confirmation(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "secret123",
                "new_password": "newStrongPass123",
                "new_password_confirm": "differentPassword123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password_confirm", response.data)


@override_settings(SECURE_SSL_REDIRECT=False)
class RecurringPaymentMonthlyCompletionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.family = Family.objects.create(name="Familia cierre mensual")
        self.other_family = Family.objects.create(name="Otra familia")
        self.user = User.objects.create_user(username="monthly-user", password="secret123")
        self.other_user = User.objects.create_user(username="other-user", password="secret123")
        self.user.profile.family = self.family
        self.user.profile.save(update_fields=["family"])
        self.other_user.profile.family = self.other_family
        self.other_user.profile.save(update_fields=["family"])
        self.category = Category.objects.create(
            family=self.family,
            name="Agua",
            icon="water",
        )
        self.month_june = Month.objects.create(family=self.family, year=2026, month=6)
        self.month_july = Month.objects.create(family=self.family, year=2026, month=7)
        self.recurring = RecurringPayment.objects.create(
            family=self.family,
            category=self.category,
            name="Agua",
            amount=Decimal("40.00"),
            due_day=10,
            start_date=date(2026, 1, 1),
            active=True,
        )
        self.client.force_authenticate(user=self.user)

    def _add_payment(self, amount, *, month=None, day=10):
        month = month or self.month_june
        return Expense.objects.create(
            month=month,
            user=self.user,
            payer=self.user,
            amount=Decimal(amount),
            category=self.category,
            recurring_payment=self.recurring,
            date=date(month.year, month.month, day),
            description="Factura de agua",
        )

    def _month_status_url(self, *, recurring=None, year=2026, month=6):
        recurring = recurring or self.recurring
        return (
            f"/api/recurring-payments/{recurring.id}/month-status/"
            f"?year={year}&month={month}"
        )

    def test_canonical_calculation_covers_pending_partial_completed_exact_and_exceeded(self):
        cases = [
            ("0.00", False, "40.00", "40.00", "pending"),
            ("37.00", False, "3.00", "3.00", "partially_paid"),
            ("37.00", True, "0.00", "3.00", "completed"),
            ("40.00", False, "0.00", "0.00", "covered"),
            ("45.00", False, "0.00", "-5.00", "exceeded"),
        ]

        for paid, completed, pending, difference, expected_status in cases:
            with self.subTest(paid=paid, completed=completed):
                amounts = calculate_recurring_payment_amounts(
                    planned_amount=Decimal("40.00"),
                    paid_amount=Decimal(paid),
                    is_completed=completed,
                )
                self.assertEqual(amounts.pending_amount, Decimal(pending))
                self.assertEqual(amounts.difference_amount, Decimal(difference))
                self.assertEqual(amounts.payment_status, expected_status)
                self.assertIsInstance(amounts.pending_amount, Decimal)
                self.assertIsInstance(amounts.difference_amount, Decimal)

    def test_complete_and_reopen_partial_payment_updates_budget_without_losing_difference(self):
        self._add_payment("37.00")

        open_budget = self.client.get("/api/budget/?year=2026&month=6")
        self.assertEqual(open_budget.status_code, 200)
        open_item = open_budget.data["recurring"][0]
        self.assertEqual(str(open_item["paid_amount"]), "37.00")
        self.assertEqual(str(open_item["pending_amount"]), "3.00")
        self.assertEqual(str(open_item["difference_amount"]), "3.00")
        self.assertEqual(open_item["payment_status"], "partially_paid")
        self.assertFalse(open_item["is_completed"])

        completed = self.client.patch(
            self._month_status_url(),
            {"is_completed": True},
            format="json",
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(str(completed.data["pending_amount"]), "0.00")
        self.assertEqual(str(completed.data["difference_amount"]), "3.00")
        self.assertEqual(completed.data["status"], "completed")

        completed_budget = self.client.get("/api/budget/?year=2026&month=6")
        item = completed_budget.data["recurring"][0]
        self.assertEqual(str(item["pending_amount"]), "0.00")
        self.assertEqual(str(item["remaining_amount"]), "0.00")
        self.assertEqual(str(item["difference_amount"]), "3.00")
        self.assertEqual(str(completed_budget.data["recurring_pending_amount"]), "0.00")
        self.assertEqual(str(completed_budget.data["total_pending_amount"]), "0.00")
        self.assertEqual(str(completed_budget.data["total_spent"]), "37.00")
        self.assertEqual(str(completed_budget.data["remaining_amount"]), "3.00")
        self.assertEqual(str(completed_budget.data["difference_amount"]), "3.00")

        reopened = self.client.patch(
            self._month_status_url(),
            {"is_completed": False},
            format="json",
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(str(reopened.data["pending_amount"]), "3.00")
        self.assertEqual(reopened.data["status"], "partially_paid")

    def test_expense_response_exposes_backend_month_calculation(self):
        payment = self._add_payment("37.00")
        self.client.patch(
            self._month_status_url(),
            {"is_completed": True},
            format="json",
        )

        response = self.client.get(f"/api/expenses/{payment.id}/")

        self.assertEqual(response.status_code, 200)
        month_state = response.data["recurring_payment_month"]
        self.assertEqual(str(month_state["paid_amount"]), "37.00")
        self.assertEqual(str(month_state["pending_amount"]), "0.00")
        self.assertEqual(str(month_state["difference_amount"]), "3.00")
        self.assertTrue(month_state["is_completed"])
        self.assertEqual(month_state["status"], "completed")

    def test_completed_occurrence_rejects_new_movements_until_reopened(self):
        self.client.patch(
            self._month_status_url(),
            {"is_completed": True},
            format="json",
        )

        rejected = self.client.post(
            "/api/expenses/",
            {
                "description": "Movimiento tardio",
                "amount": "3.00",
                "category": self.category.id,
                "recurring_payment": self.recurring.id,
                "date": "2026-06-20",
            },
            format="json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("recurring_payment", rejected.data)

        self.client.patch(
            self._month_status_url(),
            {"is_completed": False},
            format="json",
        )
        accepted = self.client.post(
            "/api/expenses/",
            {
                "description": "Movimiento tras reapertura",
                "amount": "3.00",
                "category": self.category.id,
                "recurring_payment": self.recurring.id,
                "date": "2026-06-20",
            },
            format="json",
        )
        self.assertEqual(accepted.status_code, 201)

    def test_budget_overpayment_never_has_negative_pending_amount(self):
        self._add_payment("45.00")

        response = self.client.get("/api/budget/?year=2026&month=6")

        self.assertEqual(response.status_code, 200)
        item = response.data["recurring"][0]
        self.assertEqual(str(item["pending_amount"]), "0.00")
        self.assertEqual(str(item["remaining_amount"]), "0.00")
        self.assertEqual(str(item["difference_amount"]), "-5.00")
        self.assertEqual(item["payment_status"], "exceeded")

    def test_completion_is_isolated_by_month_and_does_not_change_template(self):
        self.client.patch(
            self._month_status_url(),
            {"is_completed": True},
            format="json",
        )

        july = self.client.get(self._month_status_url(year=2026, month=7))

        self.assertEqual(july.status_code, 200)
        self.assertFalse(july.data["is_completed"])
        self.assertEqual(str(july.data["pending_amount"]), "40.00")
        self.recurring.refresh_from_db()
        self.assertTrue(self.recurring.active)
        self.assertEqual(self.recurring.amount, Decimal("40.00"))

    def test_user_cannot_complete_another_family_recurring_payment(self):
        other_category = Category.objects.create(
            family=self.other_family,
            name="Privado",
            icon="lock",
        )
        foreign_recurring = RecurringPayment.objects.create(
            family=self.other_family,
            category=other_category,
            name="Privado",
            amount=Decimal("20.00"),
            due_day=1,
            start_date=date(2026, 1, 1),
        )

        response = self.client.patch(
            self._month_status_url(recurring=foreign_recurring),
            {"is_completed": True},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            RecurringPaymentOccurrence.objects.filter(
                recurring_payment=foreign_recurring,
                month__year=2026,
                month__month=6,
            ).exists()
        )

    def test_generation_creates_a_fresh_open_occurrence_after_completed_previous_month(self):
        today = timezone.now().date()
        current_month, _ = Month.objects.get_or_create(
            family=self.family,
            year=today.year,
            month=today.month,
        )
        previous_date = today.replace(day=1) - timedelta(days=1)
        previous_month, _ = Month.objects.get_or_create(
            family=self.family,
            year=previous_date.year,
            month=previous_date.month,
        )
        self.recurring.start_date = previous_date.replace(day=1)
        self.recurring.save(update_fields=["start_date"])
        RecurringPaymentOccurrence.objects.create(
            recurring_payment=self.recurring,
            month=previous_month,
            is_completed=True,
        )

        response = self.client.post("/api/recurring/generate/")

        self.assertEqual(response.status_code, 200)
        current_occurrence = RecurringPaymentOccurrence.objects.get(
            recurring_payment=self.recurring,
            month=current_month,
        )
        self.assertFalse(current_occurrence.is_completed)

    def test_completed_occurrence_does_not_receive_generated_movement(self):
        today = timezone.now().date()
        current_month, _ = Month.objects.get_or_create(
            family=self.family,
            year=today.year,
            month=today.month,
        )
        self.recurring.start_date = today.replace(day=1)
        self.recurring.save(update_fields=["start_date"])
        RecurringPaymentOccurrence.objects.create(
            recurring_payment=self.recurring,
            month=current_month,
            is_completed=True,
        )

        response = self.client.post("/api/recurring/generate/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["completed_skipped"], 1)
        self.assertFalse(
            Expense.objects.filter(
                recurring_payment=self.recurring,
                month=current_month,
            ).exists()
        )

    def test_closed_month_cannot_be_completed_or_reopened(self):
        self.month_june.is_closed = True
        self.month_june.save(update_fields=["is_closed"])

        response = self.client.patch(
            self._month_status_url(),
            {"is_completed": True},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            RecurringPaymentOccurrence.objects.get(
                recurring_payment=self.recurring,
                month=self.month_june,
            ).is_completed
        )


@override_settings(SECURE_SSL_REDIRECT=False)
class PlannedPaymentMonthlyCompletionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="planned-month-user", password="secret123")
        self.family = self.user.profile.family
        self.category = Category.objects.create(
            family=self.family,
            name="Bebé",
            icon="baby",
        )
        self.month = Month.objects.create(family=self.family, year=2026, month=7)
        self.plan = PlannedExpensePlan.objects.create(
            family=self.family,
            category=self.category,
            name="Bebé",
            plan_type="ONGOING",
            start_month=self.month,
            created_by=self.user,
        )
        self.version = PlannedExpenseVersion.objects.create(
            plan=self.plan,
            planned_amount=Decimal("40.00"),
            valid_from=self.month,
        )
        self.client.force_authenticate(user=self.user)

    def _plan_status_url(self):
        return (
            f"/api/planned-expense-plans/{self.plan.id}/month-status/"
            "?year=2026&month=7"
        )

    def _add_plan_payment(self, amount="36.00"):
        return Expense.objects.create(
            month=self.month,
            user=self.user,
            payer=self.user,
            category=self.category,
            planned_expense_plan=self.plan,
            amount=Decimal(amount),
            date=date(2026, 7, 10),
            description="Factura bebé",
        )

    def test_plan_can_close_partial_payment_and_reopen_without_changing_planned_version(self):
        self._add_plan_payment()

        opened = self.client.get("/api/budget/?year=2026&month=7")
        item = next(row for row in opened.data["planned"] if row.get("plan_id") == self.plan.id)
        self.assertEqual(str(item["paid_amount"]), "36.00")
        self.assertEqual(str(item["pending_amount"]), "4.00")
        self.assertEqual(item["payment_status"], "partially_paid")

        completed = self.client.patch(
            self._plan_status_url(),
            {"is_completed": True},
            format="json",
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(str(completed.data["pending_amount"]), "0.00")
        self.assertEqual(str(completed.data["difference_amount"]), "4.00")
        self.assertEqual(completed.data["payment_status"], "completed")

        budget = self.client.get("/api/budget/?year=2026&month=7")
        item = next(row for row in budget.data["planned"] if row.get("plan_id") == self.plan.id)
        self.assertEqual(str(item["pending_amount"]), "0.00")
        self.assertEqual(str(budget.data["total_pending_amount"]), "0.00")
        self.version.refresh_from_db()
        self.assertEqual(self.version.planned_amount, Decimal("40.00"))

        reopened = self.client.patch(
            self._plan_status_url(),
            {"is_completed": False},
            format="json",
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(str(reopened.data["pending_amount"]), "4.00")

    def test_plan_can_close_without_payments_and_blocks_movements_until_reopened(self):
        completed = self.client.patch(
            self._plan_status_url(),
            {"is_completed": True},
            format="json",
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(str(completed.data["paid_amount"]), "0.00")
        self.assertEqual(str(completed.data["pending_amount"]), "0.00")

        rejected = self.client.post(
            "/api/expenses/",
            {
                "description": "Movimiento tardío",
                "amount": "10.00",
                "category": self.category.id,
                "planned_expense_plan": self.plan.id,
                "date": "2026-07-12",
            },
            format="json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("planned_payment", rejected.data)

    def test_legacy_planned_expense_exposes_the_same_month_status_contract(self):
        legacy_category = Category.objects.create(
            family=self.family,
            name="Colegio",
            icon="school",
        )
        legacy = PlannedExpense.objects.create(
            family=self.family,
            month=self.month,
            category=legacy_category,
            name="Colegio",
            planned_amount=Decimal("80.00"),
            created_by=self.user,
        )
        payment = Expense.objects.create(
            month=self.month,
            user=self.user,
            category=legacy_category,
            planned_expense=legacy,
            amount=Decimal("75.00"),
            date=date(2026, 7, 11),
        )
        url = f"/api/planned-expenses/{legacy.id}/month-status/?year=2026&month=7"

        completed = self.client.patch(url, {"is_completed": True}, format="json")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(str(completed.data["difference_amount"]), "5.00")

        expense_response = self.client.get(f"/api/expenses/{payment.id}/")
        self.assertEqual(expense_response.status_code, 200)
        self.assertTrue(expense_response.data["planned_payment_month"]["is_completed"])
        self.assertIsNone(expense_response.data["recurring_payment_month"])

    def test_closed_month_rejects_planned_payment_status_changes(self):
        self.month.is_closed = True
        self.month.save(update_fields=["is_closed"])

        response = self.client.patch(
            self._plan_status_url(),
            {"is_completed": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            PlannedExpenseOccurrence.objects.get(
                planned_expense_plan=self.plan,
                month=self.month,
            ).is_completed
        )


@override_settings(SECURE_SSL_REDIRECT=False)
class BudgetHardeningTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="hardening-admin", password="secret123")
        self.family = self.user.profile.family
        self.user.profile.role = "admin"
        self.user.profile.save(update_fields=["role"])
        self.category = Category.objects.create(
            family=self.family, name="Planificada", icon="📋"
        )
        self.client.force_authenticate(user=self.user)

    def test_budget_uses_calendar_order_instead_of_month_primary_keys(self):
        target = Month.objects.create(family=self.family, year=2026, month=4)
        start = Month.objects.create(family=self.family, year=2026, month=1)
        plan = PlannedExpensePlan.objects.create(
            family=self.family, category=self.category, name="Plan cronológico",
            plan_type="ONGOING", start_month=start, created_by=self.user,
        )
        PlannedExpenseVersion.objects.create(
            plan=plan, planned_amount="100.00", valid_from=start
        )

        response = self.client.get("/api/budget/?year=2026&month=4")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["month_id"], target.id)
        self.assertEqual([item["plan_id"] for item in response.data["planned"]], [plan.id])

    def test_budget_includes_one_month_plan_once_only_in_its_target_month(self):
        august = Month.objects.create(family=self.family, year=2026, month=8)
        september = Month.objects.create(family=self.family, year=2026, month=9)
        october = Month.objects.create(family=self.family, year=2026, month=10)
        plan = PlannedExpensePlan.objects.create(
            family=self.family,
            category=self.category,
            name="Plan puntual de septiembre",
            plan_type="ONE_MONTH",
            start_month=september,
            end_month=september,
            created_by=self.user,
        )
        PlannedExpenseVersion.objects.create(
            plan=plan,
            planned_amount="100.00",
            valid_from=september,
            valid_to=september,
        )
        Expense.objects.create(
            month=september,
            user=self.user,
            payer=self.user,
            category=self.category,
            planned_expense_plan=plan,
            amount="40.00",
            date=date(2026, 9, 10),
        )

        september_response = self.client.get("/api/budget/?year=2026&month=9")
        august_response = self.client.get("/api/budget/?year=2026&month=8")
        october_response = self.client.get("/api/budget/?year=2026&month=10")

        self.assertEqual(september_response.status_code, 200)
        matching_items = [
            item
            for item in september_response.data["planned"]
            if item.get("plan_id") == plan.id
        ]
        self.assertEqual(len(matching_items), 1)
        self.assertEqual(str(matching_items[0]["planned_amount"]), "100.00")
        self.assertEqual(str(matching_items[0]["paid_amount"]), "40.00")
        self.assertEqual(str(matching_items[0]["pending_amount"]), "60.00")
        self.assertEqual(str(september_response.data["total_planned"]), "100.00")
        self.assertEqual(str(september_response.data["total_spent"]), "40.00")
        self.assertFalse(
            any(item.get("plan_id") == plan.id for item in august_response.data["planned"])
        )
        self.assertFalse(
            any(item.get("plan_id") == plan.id for item in october_response.data["planned"])
        )
        self.assertEqual(august_response.data["month_id"], august.id)
        self.assertEqual(october_response.data["month_id"], october.id)

    def test_one_month_plans_calculate_unpaid_and_fully_paid_amounts(self):
        september = Month.objects.create(family=self.family, year=2026, month=9)
        unpaid_plan = PlannedExpensePlan.objects.create(
            family=self.family,
            category=self.category,
            name="Sin movimientos",
            plan_type="ONE_MONTH",
            start_month=september,
            end_month=september,
            created_by=self.user,
        )
        paid_plan = PlannedExpensePlan.objects.create(
            family=self.family,
            category=self.category,
            name="Pagado por completo",
            plan_type="ONE_MONTH",
            start_month=september,
            end_month=september,
            created_by=self.user,
        )
        for plan, amount in ((unpaid_plan, "100.00"), (paid_plan, "80.00")):
            PlannedExpenseVersion.objects.create(
                plan=plan,
                planned_amount=amount,
                valid_from=september,
                valid_to=september,
            )
        Expense.objects.create(
            month=september,
            user=self.user,
            payer=self.user,
            category=self.category,
            planned_expense_plan=paid_plan,
            amount="80.00",
            date=date(2026, 9, 15),
        )

        response = self.client.get("/api/budget/?year=2026&month=9")

        by_plan = {item["plan_id"]: item for item in response.data["planned"]}
        self.assertEqual(str(by_plan[unpaid_plan.id]["paid_amount"]), "0.00")
        self.assertEqual(str(by_plan[unpaid_plan.id]["pending_amount"]), "100.00")
        self.assertEqual(by_plan[unpaid_plan.id]["payment_status"], "pending")
        self.assertEqual(str(by_plan[paid_plan.id]["paid_amount"]), "80.00")
        self.assertEqual(str(by_plan[paid_plan.id]["pending_amount"]), "0.00")
        self.assertEqual(by_plan[paid_plan.id]["payment_status"], "covered")
        self.assertEqual(str(response.data["total_planned"]), "180.00")
        self.assertEqual(str(response.data["total_spent"]), "80.00")
        self.assertEqual(str(response.data["total_pending_amount"]), "100.00")

    def test_migrated_one_month_plan_does_not_duplicate_legacy_budget_or_occurrence(self):
        september = Month.objects.create(family=self.family, year=2026, month=9)
        legacy = PlannedExpense.objects.create(
            family=self.family,
            month=september,
            category=self.category,
            name="Plan migrado",
            planned_amount="100.00",
            created_by=self.user,
        )
        migrated_plan = PlannedExpensePlan.objects.create(
            family=self.family,
            category=self.category,
            name="Plan migrado",
            plan_type="ONE_MONTH",
            start_month=september,
            end_month=september,
            created_by=self.user,
        )
        PlannedExpenseVersion.objects.create(
            plan=migrated_plan,
            planned_amount="100.00",
            valid_from=september,
            valid_to=september,
        )

        first = self.client.get("/api/budget/?year=2026&month=9")
        second = self.client.get("/api/budget/?year=2026&month=9")

        self.assertEqual(str(first.data["total_planned"]), "100.00")
        self.assertEqual(len(first.data["planned"]), 1)
        self.assertEqual(first.data["planned"][0]["id"], legacy.id)
        self.assertEqual(str(second.data["total_planned"]), "100.00")
        self.assertEqual(
            PlannedExpenseOccurrence.objects.filter(
                planned_expense=legacy,
                month=september,
            ).count(),
            1,
        )
        self.assertFalse(
            PlannedExpenseOccurrence.objects.filter(
                planned_expense_plan=migrated_plan,
                month=september,
            ).exists()
        )

    def test_one_month_plan_is_isolated_by_family(self):
        september = Month.objects.create(family=self.family, year=2026, month=9)
        other_user = User.objects.create_user(username="other-family", password="secret123")
        other_family = other_user.profile.family
        other_category = Category.objects.create(
            family=other_family,
            name="Ajena",
            icon="🔒",
        )
        other_month = Month.objects.create(family=other_family, year=2026, month=9)
        other_plan = PlannedExpensePlan.objects.create(
            family=other_family,
            category=other_category,
            name="Plan ajeno",
            plan_type="ONE_MONTH",
            start_month=other_month,
            end_month=other_month,
            created_by=other_user,
        )
        PlannedExpenseVersion.objects.create(
            plan=other_plan,
            planned_amount="999.00",
            valid_from=other_month,
            valid_to=other_month,
        )

        response = self.client.get("/api/budget/?year=2026&month=9")

        self.assertEqual(response.data["month_id"], september.id)
        self.assertEqual(str(response.data["total_planned"]), "0")
        self.assertFalse(
            any(item.get("plan_id") == other_plan.id for item in response.data["planned"])
        )

    @override_settings(TIME_ZONE="Pacific/Kiritimati")
    def test_one_month_plan_uses_target_month_not_creation_time_or_timezone(self):
        september = Month.objects.create(family=self.family, year=2026, month=9)
        plans = []
        for name, amount, created_at in (
            ("Creado antes", "25.00", timezone.make_aware(timezone.datetime(2026, 8, 15, 12))),
            ("Creado durante", "35.00", timezone.make_aware(timezone.datetime(2026, 9, 20, 12))),
        ):
            plan = PlannedExpensePlan.objects.create(
                family=self.family,
                category=self.category,
                name=name,
                plan_type="ONE_MONTH",
                start_month=september,
                end_month=september,
                created_by=self.user,
            )
            PlannedExpensePlan.objects.filter(pk=plan.pk).update(created_at=created_at)
            PlannedExpenseVersion.objects.create(
                plan=plan,
                planned_amount=amount,
                valid_from=september,
                valid_to=september,
            )
            plans.append(plan)

        response = self.client.get("/api/budget/?year=2026&month=9")

        self.assertEqual(
            {item["plan_id"] for item in response.data["planned"]},
            {plan.id for plan in plans},
        )
        self.assertEqual(str(response.data["total_planned"]), "60.00")

    def test_each_new_plan_counts_only_its_explicitly_linked_expenses(self):
        month = Month.objects.create(family=self.family, year=2026, month=6)
        plans = []
        for name, amount in (("Plan A", "100.00"), ("Plan B", "200.00")):
            plan = PlannedExpensePlan.objects.create(
                family=self.family, category=self.category, name=name,
                plan_type="ONGOING", start_month=month, created_by=self.user,
            )
            PlannedExpenseVersion.objects.create(
                plan=plan, planned_amount=amount, valid_from=month
            )
            plans.append(plan)

        for plan, amount in zip(plans, ("20.00", "30.00")):
            Expense.objects.create(
                month=month, user=self.user, payer=self.user, category=self.category,
                planned_expense_plan=plan, amount=amount, date=date(2026, 6, 10),
            )

        response = self.client.get("/api/budget/?year=2026&month=6")

        spent_by_plan = {
            item["plan_id"]: str(item["spent_amount"])
            for item in response.data["planned"]
        }
        self.assertEqual(spent_by_plan, {plans[0].id: "20.00", plans[1].id: "30.00"})
        self.assertEqual(str(response.data["total_spent"]), "50.00")

    def test_budget_actual_spent_and_status_distinguish_covered_from_exceeded(self):
        month = Month.objects.create(family=self.family, year=2026, month=7)
        recurring = RecurringPayment.objects.create(
            family=self.family,
            category=self.category,
            name="Seguro",
            amount="40.00",
            due_day=5,
            start_date=date(2026, 1, 1),
        )
        Expense.objects.create(
            month=month,
            user=self.user,
            payer=self.user,
            category=self.category,
            recurring_payment=recurring,
            amount="40.00",
            date=date(2026, 7, 5),
        )

        covered = self.client.get("/api/budget/?year=2026&month=7")

        self.assertEqual(covered.status_code, 200)
        self.assertEqual(covered.data["status"], "ok")
        self.assertEqual(str(covered.data["actual_spent"]), "40.00")
        self.assertEqual(str(covered.data["total_spent"]), "40.00")
        self.assertEqual(str(covered.data["remaining_amount"]), "0.00")

        Expense.objects.create(
            month=month,
            user=self.user,
            payer=self.user,
            category=self.category,
            amount="10.00",
            date=date(2026, 7, 8),
            description="Compra no planificada",
        )

        exceeded = self.client.get("/api/budget/?year=2026&month=7")

        self.assertEqual(exceeded.data["status"], "over")
        self.assertEqual(str(exceeded.data["actual_spent"]), "50.00")
        self.assertEqual(str(exceeded.data["unplanned_total"]), "10.00")
        self.assertEqual(str(exceeded.data["remaining_amount"]), "-10.00")

    def test_budget_exposes_compatible_budget_pending_and_cash_metrics(self):
        month = Month.objects.create(family=self.family, year=2026, month=9)
        recurring = RecurringPayment.objects.create(
            family=self.family,
            category=self.category,
            name="Fijo",
            amount="100.00",
            due_day=5,
            start_date=date(2026, 1, 1),
        )
        plan = PlannedExpensePlan.objects.create(
            family=self.family,
            category=self.category,
            name="Plan mensual",
            plan_type="ONGOING",
            start_month=month,
            created_by=self.user,
        )
        PlannedExpenseVersion.objects.create(
            plan=plan,
            planned_amount="200.00",
            valid_from=month,
        )
        Income.objects.create(
            month=month,
            user=self.user,
            amount="1000.00",
            category=self.category,
            date=date(2026, 9, 1),
        )
        Expense.objects.create(
            month=month,
            user=self.user,
            payer=self.user,
            category=self.category,
            recurring_payment=recurring,
            amount="60.00",
            date=date(2026, 9, 5),
        )
        Expense.objects.create(
            month=month,
            user=self.user,
            payer=self.user,
            category=self.category,
            planned_expense_plan=plan,
            amount="50.00",
            date=date(2026, 9, 10),
        )
        Expense.objects.create(
            month=month,
            user=self.user,
            payer=self.user,
            category=self.category,
            amount="30.00",
            date=date(2026, 9, 12),
        )

        response = self.client.get("/api/budget/?year=2026&month=9")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["total_planned"]), "300.00")
        self.assertEqual(str(response.data["planned_paid_amount"]), "110.00")
        self.assertEqual(str(response.data["planned_pending_amount"]), "190.00")
        self.assertEqual(str(response.data["total_pending_amount"]), "190.00")
        self.assertEqual(str(response.data["unplanned_total"]), "30.00")
        self.assertEqual(str(response.data["actual_spent"]), "140.00")
        self.assertEqual(str(response.data["total_spent"]), "140.00")
        self.assertEqual(str(response.data["budget_variance"]), "160.00")
        self.assertEqual(str(response.data["remaining_amount"]), "160.00")
        self.assertEqual(str(response.data["difference_amount"]), "160.00")
        self.assertEqual(str(response.data["actual_income"]), "1000.00")
        self.assertEqual(str(response.data["cash_balance"]), "860.00")
        self.assertEqual(str(response.data["percentage_used"]), "46.67")

    def test_budget_without_planning_marks_real_spending_as_exceeded(self):
        month = Month.objects.create(family=self.family, year=2026, month=8)
        Expense.objects.create(
            month=month,
            user=self.user,
            payer=self.user,
            category=self.category,
            amount="25.00",
            date=date(2026, 8, 3),
        )

        response = self.client.get("/api/budget/?year=2026&month=8")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "over")
        self.assertEqual(str(response.data["actual_spent"]), "25.00")
        self.assertEqual(str(response.data["remaining_amount"]), "-25.00")

    def test_planned_expense_adjustment_closes_previous_version(self):
        january = Month.objects.create(family=self.family, year=2026, month=1)
        march = Month.objects.create(family=self.family, year=2026, month=3)
        april = Month.objects.create(family=self.family, year=2026, month=4)
        plan = PlannedExpensePlan.objects.create(
            family=self.family, category=self.category, name="Plan versionado",
            plan_type="ONGOING", start_month=january, created_by=self.user,
        )
        first = PlannedExpenseVersion.objects.create(
            plan=plan, planned_amount="100.00", valid_from=january
        )

        response = self.client.patch(
            f"/api/planned-expense-plans/{plan.id}/",
            {"planned_amount": "150.00", "effective_month": april.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.valid_to_id, march.id)
        current = PlannedExpenseVersion.objects.get(plan=plan, valid_from=april)
        self.assertEqual(current.planned_amount, Decimal("150.00"))

    def test_member_can_read_configuration_but_cannot_modify_it(self):
        self.user.profile.role = "member"
        self.user.profile.save(update_fields=["role"])

        self.assertEqual(self.client.get("/api/categories/").status_code, 200)
        response = self.client.post(
            "/api/categories/", {"name": "Bloqueada", "icon": "🔒"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_budget_rejects_invalid_month_without_creating_it(self):
        response = self.client.get("/api/budget/?year=2026&month=13")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Month.objects.filter(family=self.family, month=13).exists())
