"""Cross-domain cash balance regression for the integrated feature branches."""
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import Category, Expense, Income, IncomePlanVersion, Month


@override_settings(ASSISTANT_ENABLED=True, ASSISTANT_PROVIDER='mock', SECURE_SSL_REDIRECT=False)
class IntegratedMoneyFlowTests(TestCase):
    def test_actual_receipt_financed_payment_and_confirmed_nilo_batch_count_once(self):
        user = User.objects.create_user(username='integration-admin')
        user.profile.role = 'admin'
        user.profile.save()
        family = user.profile.family
        category = Category.objects.create(family=family, name='Prueba configurable')
        month = Month.objects.create(family=family, year=2026, month=11)
        client = APIClient()
        client.force_authenticate(user)

        def post(url, data, expected=200):
            response = client.post(url, data, format='json')
            self.assertEqual(response.status_code, expected, response.data)
            return response.data

        def balance():
            response = client.get('/api/budget/?year=2026&month=11')
            self.assertEqual(response.status_code, 200)
            return Decimal(response.data['cash_balance'])

        plan = post('/api/income-plans/', {'name': 'Sueldo', 'category': category.pk,
                    'plan_type': 'ONGOING', 'start_month': month.pk, 'planned_amount': '1000'}, 201)
        self.assertEqual(balance(), Decimal('0'))
        receipt_url = f'/api/income-plans/{plan["id"]}/record-receipt/?year=2026&month=11'
        receipt = {'amount': '1100', 'date': '2026-11-10'}
        post(receipt_url, receipt)
        post(receipt_url, receipt)
        self.assertEqual(balance(), Decimal('1100'))
        self.assertEqual(Income.objects.count(), 1)
        self.assertEqual(IncomePlanVersion.objects.get(plan_id=plan['id']).planned_amount, Decimal('1000'))

        purchase = post('/api/financed-purchases/', {'idempotency_key': str(uuid4()), 'name': 'Compra financiada', 'category': category.pk,
                        'purchase_date': '2026-11-01', 'first_due_date': '2026-11-15',
                        'total_amount': '300', 'installment_count': 3}, 201)
        self.assertEqual(balance(), Decimal('1100'))
        installment = purchase['installments'][0]['id']
        payment_url = f'/api/financing-installments/{installment}/payments/'
        payment = {'amount': '40', 'date': '2026-11-15', 'idempotency_key': str(uuid4())}
        post(payment_url, payment, 201)
        post(payment_url, payment)
        self.assertEqual(balance(), Decimal('1060'))

        proposal = post('/api/assistant/movement-proposals/', {'movements': [
            {'kind': 'expense', 'amount': '10', 'date': '2026-11-16', 'category': category.pk},
            {'kind': 'income', 'amount': '50', 'date': '2026-11-16', 'category': category.pk},
        ]}, 201)
        self.assertEqual(balance(), Decimal('1060'))
        confirm_url = f'/api/assistant/movement-proposals/{proposal["id"]}/confirm/'
        post(confirm_url, {'confirmed': True})
        post(confirm_url, {'confirmed': True})
        self.assertEqual(balance(), Decimal('1100'))
        self.assertEqual(Income.objects.count(), 2)
        self.assertEqual(Expense.objects.count(), 2)
        purchase = client.get(f'/api/financed-purchases/{purchase["id"]}/').data
        self.assertEqual(Decimal(purchase['outstanding_amount']), Decimal('260'))

        post(f'/api/income-plans/{plan["id"]}/change-planned-amount/?year=2026&month=12', {'amount': '1200'})
        self.assertEqual(balance(), Decimal('1100'))
        month.is_closed = True
        month.save()
        post(receipt_url, receipt, 400)
        post(payment_url, {**payment, 'idempotency_key': str(uuid4())}, 400)
        self.assertEqual(balance(), Decimal('1100'))
