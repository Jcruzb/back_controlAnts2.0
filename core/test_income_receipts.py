"""Separate actual receipts from forward planning, preserving the legacy API."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from core.models import Category, Family, Income, IncomePlan, IncomePlanVersion, Month, Profile


class IncomeFixtures:
    def setUp(self):
        self.family = Family.objects.create(name='Receipt tests')
        self.user = User.objects.create_user(username='receipt-admin')
        Profile.objects.update_or_create(user=self.user, defaults={'family': self.family, 'role': 'admin'})
        self.member = User.objects.create_user(username='receipt-member')
        Profile.objects.update_or_create(user=self.member, defaults={'family': self.family, 'role': 'member'})
        self.category = Category.objects.create(family=self.family, name='Salary', icon='salary')
        self.months = {m: Month.objects.create(family=self.family, year=2026, month=m) for m in range(1, 13)}
        self.plan = IncomePlan.objects.create(family=self.family, category=self.category, name='Salary',
            plan_type='ONGOING', start_month=self.months[1], created_by=self.user)
        IncomePlanVersion.objects.create(plan=self.plan, planned_amount='1000.00', valid_from=self.months[1])
        self.user.refresh_from_db()
        self.member.refresh_from_db()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def post(self, action='record-receipt', month=8, **data):
        return self.client.post(f'/api/income-plans/{self.plan.pk}/{action}/?year=2026&month={month}', data, format='json')


@override_settings(SECURE_SSL_REDIRECT=False)
class IncomeReceiptTests(IncomeFixtures, TestCase):
    def test_exceptional_receipts_preserve_versions_and_budget_counts_once(self):
        for amount in ('850.00', '1000.00', '1250.00'):
            with self.subTest(amount=amount):
                Income.objects.all().delete()
                response = self.post(amount=amount, date='2026-08-10')
                self.assertEqual(response.status_code, 200, response.data)
                self.assertTrue(response.data['created'])
                income = Income.objects.get(pk=response.data['income_id'])
                self.assertEqual(income.amount, Decimal(amount))
                self.assertEqual(IncomePlanVersion.objects.get(plan=self.plan).planned_amount, Decimal('1000'))
                retry = self.post(amount=amount, date='2026-08-10')
                self.assertEqual(retry.status_code, 200)
                self.assertFalse(retry.data['created'])
                self.assertEqual(retry.data['income_id'], income.pk)
                self.assertEqual(Income.objects.count(), 1)
                budget = self.client.get('/api/budget/?year=2026&month=8')
                self.assertEqual(Decimal(str(budget.data['actual_income'])), Decimal(amount))
                self.assertEqual(Decimal(str(budget.data['cash_balance'])), Decimal(amount))

    def test_different_retry_conflicts_without_overwriting(self):
        self.post(amount='900', date='2026-08-10', description='Original')
        for data in ({'amount': '901', 'date': '2026-08-10', 'description': 'Original'},
                     {'amount': '900', 'date': '2026-08-11', 'description': 'Original'},
                     {'amount': '900', 'date': '2026-08-10', 'description': 'Changed'}):
            self.assertEqual(self.post(**data).status_code, 409)
        self.assertEqual(Income.objects.count(), 1)
        self.assertEqual(Income.objects.get().description, 'Original')

    def test_change_plan_does_not_create_or_modify_receipt(self):
        self.post(amount='900', date='2026-08-10')
        response = self.post('change-planned-amount', amount='1200')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Income.objects.get().amount, Decimal('900'))
        response = self.post('change-planned-amount', month=9, amount='1400')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Income.objects.count(), 1)
        for month, expected in ((7, '1000.00'), (8, '1200.00'), (9, '1400.00')):
            response = self.client.get(f'/api/income-plans/month/?year=2026&month={month}')
            self.assertEqual(response.data['results'][0]['planned_amount'], expected)

    def test_future_versions_are_preserved(self):
        self.post('change-planned-amount', month=11, amount='1500')
        self.post('change-planned-amount', month=8, amount='1200')
        versions = list(self.plan.versions.order_by('valid_from__month'))
        self.assertEqual([(v.valid_from.month, v.valid_to.month if v.valid_to else None) for v in versions], [(1, 7), (8, 10), (11, None)])
        self.assertFalse(Income.objects.exists())

    def test_member_can_receive_but_cannot_configure(self):
        self.client.force_authenticate(self.member)
        self.assertEqual(self.post(amount='900', date='2026-08-10').status_code, 200)
        self.assertEqual(self.post('change-planned-amount', amount='1200').status_code, 403)

    def test_other_family_cannot_read_or_mutate_plan(self):
        family = Family.objects.create(name='Other')
        user = User.objects.create_user(username='other-admin')
        Profile.objects.update_or_create(user=user, defaults={'family': family, 'role': 'admin'})
        user.refresh_from_db()
        self.client.force_authenticate(user)
        self.assertEqual(self.post(amount='900', date='2026-08-10').status_code, 404)
        self.assertEqual(self.post('change-planned-amount', amount='1200').status_code, 404)
        self.assertFalse(Income.objects.exists())

    def test_closed_month_rejects_both_operations(self):
        self.months[8].is_closed = True
        self.months[8].save()
        self.assertEqual(self.post(amount='900', date='2026-08-10').status_code, 400)
        self.assertEqual(self.post('change-planned-amount', amount='1200').status_code, 400)
        self.assertFalse(Income.objects.exists())
        self.assertEqual(self.plan.versions.count(), 1)

    def test_invalid_amounts_and_dates_do_not_write(self):
        for amount in ('NaN', 'Infinity', '-1', '0', '0.001', '99999999999', None, 'abc'):
            self.assertEqual(self.post(amount=amount, date='2026-08-10').status_code, 400)
            self.assertEqual(self.post('change-planned-amount', amount=amount).status_code, 400)
        for date in ('2026-09-01', '2026-08-32', None, 'invalid'):
            self.assertEqual(self.post(amount='900', date=date).status_code, 400)
        self.assertFalse(Income.objects.exists())
        self.assertEqual(self.plan.versions.count(), 1)

    def test_inactive_and_missing_version_rejected(self):
        self.plan.active = False
        self.plan.save()
        self.assertEqual(self.post(amount='900', date='2026-08-10').status_code, 400)
        self.assertEqual(self.post('change-planned-amount', amount='1200').status_code, 400)
        self.plan.active = True
        self.plan.save()
        self.plan.versions.all().delete()
        self.assertEqual(self.post(amount='900', date='2026-08-10').status_code, 400)

    def test_create_plan_never_creates_receipt_and_closed_month_is_rejected(self):
        payload = {'name': 'Second salary', 'category': self.category.pk, 'plan_type': 'ONGOING',
                   'start_month': self.months[8].pk, 'planned_amount': '1200'}
        response = self.client.post('/api/income-plans/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(Income.objects.exists())
        self.months[8].is_closed = True
        self.months[8].save()
        self.assertEqual(self.client.post('/api/income-plans/', payload, format='json').status_code, 400)
        self.assertEqual(IncomePlan.objects.count(), 2)

    def test_session_auth_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(f'/api/income-plans/{self.plan.pk}/record-receipt/?year=2026&month=8',
                               {'amount': '900', 'date': '2026-08-10'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Income.objects.exists())


@override_settings(SECURE_SSL_REDIRECT=False)
class ConcurrentIncomeReceiptTests(IncomeFixtures, TransactionTestCase):
    def test_concurrent_identical_requests_create_one_receipt(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Row-lock concurrency requires PostgreSQL')
        barrier = Barrier(2)
        def receive():
            client = APIClient()
            client.force_authenticate(User.objects.get(pk=self.user.pk))
            try:
                barrier.wait(timeout=10)
                response = client.post(f'/api/income-plans/{self.plan.pk}/record-receipt/?year=2026&month=8',
                                       {'amount': '900', 'date': '2026-08-10'}, format='json')
                return response.status_code, response.data
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: receive(), range(2)))
        self.assertEqual([status for status, _ in results], [200, 200], results)
        self.assertEqual(len({data['income_id'] for _, data in results}), 1)
        self.assertEqual(Income.objects.count(), 1)
