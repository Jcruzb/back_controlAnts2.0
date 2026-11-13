from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4
from django.contrib.auth.models import User
from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from core.models import Category, Expense, Month, FinancedPurchase, FinancingPayment

class FinancingSetup:
    def setUp(self):
        self.user = User.objects.create_user(username='finance-admin')
        self.user.profile.role = 'admin'
        self.user.profile.save()
        self.family = self.user.profile.family
        self.category = Category.objects.create(family=self.family, name='Compras')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {'name': 'Ordenador', 'category': self.category.id, 'purchase_date': '2026-01-10', 'first_due_date': '2026-01-31', 'total_amount': '100.00', 'installment_count': 3}
    def purchase(self):
        result = self.client.post('/api/financed-purchases/', self.payload, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        return result.data
    def pay(self, row, amount='10.00', key=None, **extra):
        return self.client.post(f'/api/financing-installments/{row}/payments/', {'amount': amount, 'date': '2026-01-31', 'idempotency_key': str(key or uuid4()), **extra}, format='json')

@override_settings(SECURE_SSL_REDIRECT=False)
class FinancingTests(FinancingSetup, TestCase):
    def test_schedule_rounding_and_no_cash_on_creation(self):
        purchase = self.purchase()
        self.assertEqual([row['amount'] for row in purchase['installments']], ['33.33', '33.33', '33.34'])
        self.assertEqual([str(row['due_date']) for row in purchase['installments']], ['2026-01-31', '2026-02-28', '2026-03-31'])
        self.assertEqual(Expense.objects.count(), 0)
        self.assertEqual(purchase['outstanding_amount'], '100.00')
    def test_partial_payment_retry_conflict_and_cash_total(self):
        row = self.purchase()['installments'][0]['id']; key = uuid4()
        first = self.pay(row, key=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.pay(row, key=key).status_code, 200)
        self.assertEqual(self.pay(row, amount='11.00', key=key).status_code, 409)
        self.assertEqual(self.pay(row, amount='24.00').status_code, 400)
        self.assertEqual(Expense.objects.count(), 1)
        budget = self.client.get('/api/budget/?year=2026&month=1').data
        self.assertEqual(Decimal(budget['actual_spent']), Decimal('10'))
        self.assertEqual(Decimal(budget['cash_balance']), Decimal('-10'))
        purchase = self.client.get('/api/financed-purchases/').data[0]
        self.assertEqual(Decimal(purchase['outstanding_amount']), Decimal('90'))
    def test_linked_expense_cannot_be_modified_or_deleted(self):
        expense = self.pay(self.purchase()['installments'][0]['id']).data['expense_id']
        self.assertEqual(self.client.patch(f'/api/expenses/{expense}/', {'amount': '2.00'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/expenses/{expense}/').status_code, 400)
        self.assertEqual(Expense.objects.get(pk=expense).amount, Decimal('10'))
    def test_family_isolation_and_role(self):
        row = self.purchase()['installments'][0]['id']
        outsider = User.objects.create_user(username='outsider')
        self.assertEqual(self.pay(row, payer=outsider.id).status_code, 404)
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get('/api/financed-purchases/').data, [])
        self.assertEqual(self.pay(row).status_code, 404)
        outsider.profile.family = self.family; outsider.profile.role = 'member'; outsider.profile.save()
        self.assertEqual(self.client.post('/api/financed-purchases/', self.payload, format='json').status_code, 403)
        self.assertEqual(self.pay(row).status_code, 201)
    def test_closed_months_and_input_validation(self):
        row = self.purchase()['installments'][0]['id']
        Month.objects.filter(family=self.family, year=2026, month=1).update(is_closed=True)
        self.assertEqual(self.pay(row).status_code, 400)
        self.assertEqual(self.client.post('/api/financed-purchases/', self.payload, format='json').status_code, 400)
        self.assertEqual(Expense.objects.count(), 0)
    def test_cross_family_category_and_card_rejected(self):
        outsider = User.objects.create_user(username='other')
        category = Category.objects.create(family=outsider.profile.family, name='Other')
        self.assertEqual(self.client.post('/api/financed-purchases/', {**self.payload, 'category': category.id}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/financed-purchases/', {**self.payload, 'total_amount': '0.02'}, format='json').status_code, 400)

@override_settings(SECURE_SSL_REDIRECT=False)
class FinancingConcurrencyTests(FinancingSetup, TransactionTestCase):
    def test_simultaneous_retry_creates_one_expense(self):
        if connection.vendor != 'postgresql': self.skipTest('Requires PostgreSQL row locks')
        row = self.purchase()['installments'][0]['id']; key = str(uuid4()); user_id = self.user.id
        def send(_):
            close_old_connections()
            try:
                client = APIClient(); client.force_authenticate(User.objects.get(pk=user_id))
                return client.post(f'/api/financing-installments/{row}/payments/', {'amount': '33.33', 'date': '2026-01-31', 'idempotency_key': key}, format='json').status_code
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(send, range(2))), [200, 201])
        self.assertEqual(FinancingPayment.objects.count(), 1)
        self.assertEqual(Expense.objects.count(), 1)
