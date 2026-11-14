from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient
from core.models import (Category, Expense, Month, FinancedPurchase, FinancingPayment,
    RecurringPayment, RecurringPaymentOccurrence, PlannedExpense, PlannedExpenseOccurrence)
from core.services.expense_financing_conversion import snapshot


class ConversionFixtures:
    def setUp(self):
        self.user = User.objects.create_user(username='conversion-admin')
        self.user.profile.role = 'admin'; self.user.profile.save()
        self.family = self.user.profile.family
        self.category = Category.objects.create(family=self.family, name='Configurable')
        self.month = Month.objects.create(family=self.family, year=2026, month=11)
        self.expense = Expense.objects.create(user=self.user, payer=self.user, month=self.month,
            category=self.category, amount='40.00', date=date(2026,11,10), description='Original')
        self.expense.refresh_from_db()
        self.client = APIClient(); self.client.force_authenticate(self.user)
        self.url = f'/api/expenses/{self.expense.pk}/convert-to-financing/'
        self.payload = {'confirmed': True, 'idempotency_key': str(uuid4()), 'name': 'Compra',
            'credit_account': None, 'total_amount': '140.00', 'installment_count': 3,
            'first_due_date': '2026-12-31', 'expected_expense': snapshot(self.expense)}
    def convert(self, **changes):
        return self.client.post(self.url, {**self.payload, **changes}, format='json')


@override_settings(SECURE_SSL_REDIRECT=False)
class ConversionTests(ConversionFixtures, TestCase):
    def test_conversion_preserves_every_expense_field_and_cash(self):
        before = Expense.objects.filter(pk=self.expense.pk).values().get()
        result = self.convert()
        self.assertEqual(result.status_code, 201, result.data)
        data = result.data
        self.assertEqual(data['paid_amount'], '40.00')
        self.assertEqual(data['outstanding_amount'], '100.00')
        self.assertEqual([row['amount'] for row in data['installments']], ['33.33','33.33','33.34'])
        self.assertEqual([str(row['due_date']) for row in data['installments']], ['2026-12-31','2027-01-31','2027-02-28'])
        self.assertEqual(data['initial_payment']['expense_id'], self.expense.pk)
        self.assertEqual(Expense.objects.filter(pk=self.expense.pk).values().get(), before)
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(Decimal(self.client.get('/api/budget/?year=2026&month=11').data['cash_balance']), Decimal('-40'))
        dto = self.client.get(f'/api/expenses/{self.expense.pk}/').data
        self.assertTrue(dto['financing']['is_initial_payment'])
        self.assertEqual(dto['financing']['purchase_id'], data['id'])
        self.assertEqual(self.convert().status_code, 200)
        self.assertEqual(self.convert(total_amount='141').status_code, 409)
        self.assertEqual(self.convert(idempotency_key=str(uuid4())).status_code, 409)
        self.assertEqual(FinancedPurchase.objects.count(), 1)
        self.assertEqual(self.client.patch(f'/api/expenses/{self.expense.pk}/', {'amount':'41'}, format='json').status_code,400)
        self.assertEqual(self.client.delete(f'/api/expenses/{self.expense.pk}/').status_code,400)
        row = data['installments'][0]
        payment = self.client.post(f'/api/financing-installments/{row["id"]}/payments/',
            {'amount':'10', 'date':'2026-12-31','idempotency_key':str(uuid4())}, format='json')
        self.assertEqual(payment.status_code,201,payment.data)
        purchase = self.client.get(f'/api/financed-purchases/{data["id"]}/').data
        self.assertEqual(purchase['paid_amount'],'50.00')
        self.assertEqual(purchase['outstanding_amount'],'90.00')

    def test_imported_null_category_is_visible_and_preserved(self):
        # Simulate historical nullable schema in this test's rollback transaction.
        with connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cursor.execute('ALTER TABLE core_expense ALTER COLUMN category_id DROP NOT NULL')
            cursor.execute('SET CONSTRAINTS ALL DEFERRED')
        Expense.objects.filter(pk=self.expense.pk).update(category=None)
        self.expense.refresh_from_db()
        self.payload['expected_expense']=snapshot(self.expense)
        dto=self.client.get(f'/api/expenses/{self.expense.pk}/')
        self.assertEqual(dto.status_code,200)
        self.assertIsNone(dto.data['category'])
        self.assertEqual(self.convert().status_code,400)
        result=self.convert(category=self.category.pk)
        self.assertEqual(result.status_code,201,result.data)
        self.assertEqual(result.data['category'],self.category.pk)
        self.expense.refresh_from_db(); self.assertIsNone(self.expense.category_id)
        self.assertEqual(Expense.objects.count(),1)

    def test_paid_in_full_has_no_future_installments(self):
        response = self.convert(total_amount='40', installment_count=0, first_due_date=None)
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['installments'],[])
        self.assertEqual(response.data['outstanding_amount'],'0.00')
        self.assertEqual(response.data['first_due_date'],None)
        self.assertEqual(Expense.objects.count(),1)

    def test_rejects_stale_snapshot_bad_values_and_nonliteral_consent(self):
        for changes in ({'total_amount':'39'}, {'installment_count':0}, {'first_due_date':'2026-11-10'},
            {'confirmed':'true'}, {'confirmed':False}, {'payer':self.user.pk},
            {'total_amount':'40.01','installment_count':3}, {'first_due_date':'9999-12-31'}):
            with self.subTest(changes=changes): self.assertEqual(self.convert(**changes).status_code,400)
        self.expense.description='Changed'; self.expense.save()
        self.assertEqual(self.convert().status_code,409)
        self.assertFalse(FinancedPurchase.objects.exists())

    def test_role_tenant_card_and_category_boundaries(self):
        from core.models import CreditAccount
        other = User.objects.create_user(username='other-conversion')
        card = CreditAccount.objects.create(family=other.profile.family, name='Other')
        self.assertEqual(self.convert(credit_account=card.pk).status_code,404)
        category = Category.objects.create(family=self.family, name='Different')
        self.assertEqual(self.convert(category=category.pk).status_code,400)
        self.client.force_authenticate(other)
        self.assertEqual(self.convert().status_code,403)
        other.profile.role='admin'; other.profile.save()
        self.assertEqual(self.convert().status_code,404)
        self.assertFalse(FinancedPurchase.objects.exists())

    def test_month_and_completed_occurrence_guards_preserve_links(self):
        self.month.is_closed=True; self.month.save()
        self.assertEqual(self.convert().status_code,400)
        self.month.is_closed=False; self.month.save()
        planned=PlannedExpense.objects.create(family=self.family,month=self.month,category=self.category,planned_amount='100')
        self.expense.planned_expense=planned; self.expense.save()
        occurrence=PlannedExpenseOccurrence.objects.create(month=self.month,planned_expense=planned,is_completed=True)
        self.payload['expected_expense']=snapshot(self.expense)
        self.assertEqual(self.convert().status_code,400)
        occurrence.is_completed=False; occurrence.save()
        self.assertEqual(self.convert().status_code,201)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.planned_expense_id,planned.pk)

    def test_completed_recurring_occurrence_rejected_then_link_preserved(self):
        recurring=RecurringPayment.objects.create(family=self.family,category=self.category,
            name='Fixed',amount='100',due_day=10,start_date=date(2026,1,1))
        self.expense.recurring_payment=recurring; self.expense.is_recurring=True; self.expense.save()
        self.payload['expected_expense']=snapshot(self.expense)
        occurrence=RecurringPaymentOccurrence.objects.create(month=self.month,recurring_payment=recurring,is_completed=True)
        self.assertEqual(self.convert().status_code,400)
        occurrence.is_completed=False; occurrence.save()
        self.assertEqual(self.convert().status_code,201)
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.recurring_payment_id,recurring.pk)
        self.assertTrue(self.expense.is_recurring)

    def test_conversion_failure_rolls_back_all_new_rows(self):
        with patch('core.services.expense_financing_conversion.FinancingInstallment.objects.bulk_create',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError): self.convert()
        self.assertFalse(FinancedPurchase.objects.exists())
        self.assertFalse(FinancingPayment.objects.exists())
        self.assertEqual(Expense.objects.count(),1)

    def test_normal_purchase_still_rejects_null_date_and_zero_count(self):
        normal={'name':'Normal','category':self.category.pk,'purchase_date':'2026-11-01','total_amount':'100',
                'installment_count':1,'first_due_date':'2026-12-01','idempotency_key':str(uuid4())}
        for changes in ({'first_due_date':None},{'installment_count':0}):
            self.assertEqual(self.client.post('/api/financed-purchases/',{**normal,**changes},format='json').status_code,400)
        normal.pop('first_due_date')
        self.assertEqual(self.client.post('/api/financed-purchases/',normal,format='json').status_code,400)


@override_settings(SECURE_SSL_REDIRECT=False)
class ConversionConcurrencyTests(ConversionFixtures, TransactionTestCase):
    def sender(self, method='post', payload=None, url=None):
        try:
            client=APIClient(); client.force_authenticate(User.objects.get(pk=self.user.pk))
            return getattr(client,method)(url or self.url,payload or self.payload,format='json').status_code
        finally: connections.close_all()

    def test_concurrent_retry_creates_one_purchase(self):
        barrier=Barrier(2)
        def run(): barrier.wait(timeout=5); return self.sender()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:run(),range(2)))
        self.assertEqual(sorted(results),[200,201])
        self.assertEqual(Expense.objects.count(),1)
        self.assertEqual(FinancedPurchase.objects.count(),1)

    def test_waiting_edit_and_delete_cannot_bypass_financing_guard(self):
        original_create=FinancingPayment.objects.create
        created, release=Event(),Event()
        def blocked_create(*args,**kwargs):
            result=original_create(*args,**kwargs); created.set()
            if not release.wait(timeout=8): raise RuntimeError('test lock timeout')
            return result
        for method in ('patch','delete'):
            # Each iteration uses its own original movement.
            if method=='delete':
                self.expense=Expense.objects.create(user=self.user,payer=self.user,month=self.month,category=self.category,
                    amount='40',date=date(2026,11,10),description='Original')
                self.expense.refresh_from_db()
                self.url=f'/api/expenses/{self.expense.pk}/convert-to-financing/'
                self.payload.update(idempotency_key=str(uuid4()),expected_expense=snapshot(self.expense))
            created.clear(); release.clear(); waiting=Event()
            def mutate():
                def observe(execute,sql,params,many,context):
                    if 'FOR UPDATE' in sql and 'core_expense' in sql: waiting.set()
                    return execute(sql,params,many,context)
                with connection.execute_wrapper(observe):
                    return self.sender(method,{'amount':'41'},f'/api/expenses/{self.expense.pk}/')
            with patch('core.services.expense_financing_conversion.FinancingPayment.objects.create',side_effect=blocked_create):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    conversion=pool.submit(self.sender)
                    self.assertTrue(created.wait(timeout=5))
                    mutation=pool.submit(mutate)
                    try: self.assertTrue(waiting.wait(timeout=5))
                    finally: release.set()
                    self.assertEqual(conversion.result(timeout=5),201)
                    self.assertEqual(mutation.result(timeout=5),400)
            self.expense.refresh_from_db(); self.assertEqual(self.expense.amount,Decimal('40'))

    def test_edit_committed_before_waiting_conversion_rejects_stale_snapshot(self):
        locked, release = Event(), Event()
        def edit():
            try:
                with transaction.atomic():
                    row=Expense.objects.select_for_update().get(pk=self.expense.pk)
                    row.amount=Decimal('45'); row.save(update_fields=['amount'])
                    locked.set()
                    if not release.wait(timeout=8): raise RuntimeError('test timeout')
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            editing=pool.submit(edit)
            self.assertTrue(locked.wait(timeout=5))
            converting=pool.submit(self.sender)
            release.set()
            editing.result(timeout=5)
            self.assertEqual(converting.result(timeout=5),409)
        self.assertFalse(FinancedPurchase.objects.exists())
        self.expense.refresh_from_db(); self.assertEqual(self.expense.amount,Decimal('45'))

    def test_date_edit_new_month_and_conversion_do_not_deadlock_on_family_fk(self):
        from core.serializers.expense_serializer import ExpenseSerializer
        original_update = ExpenseSerializer.update
        updated, family_locked = Event(), Event()
        def hold_update(*args, **kwargs):
            result = original_update(*args, **kwargs)
            updated.set()
            if not family_locked.wait(timeout=5): raise RuntimeError('conversion did not lock family')
            return result
        def convert():
            def observe(execute, sql, params, many, context):
                result = execute(sql, params, many, context)
                if 'core_family' in sql and 'FOR NO KEY UPDATE' in sql: family_locked.set()
                return result
            with connection.execute_wrapper(observe): return self.sender()
        with patch.object(ExpenseSerializer, 'update', hold_update):
            with ThreadPoolExecutor(max_workers=2) as pool:
                editing=pool.submit(self.sender,'patch',{'date':'2026-12-10'},f'/api/expenses/{self.expense.pk}/')
                self.assertTrue(updated.wait(timeout=5))
                conversion=pool.submit(convert)
                self.assertEqual(editing.result(timeout=8),200)
                self.assertEqual(conversion.result(timeout=8),409)
        self.assertFalse(FinancedPurchase.objects.exists())
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.date,date(2026,12,10))
