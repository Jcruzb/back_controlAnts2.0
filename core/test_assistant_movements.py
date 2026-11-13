from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core.models import Category, Expense, Family, FamilyCategoryAlias, Income, Month, MovementProposal


class MovementFixtures:
    def setUp(self):
        self.user = User.objects.create_user(username='nilo-user')
        self.family = self.user.profile.family
        self.category = Category.objects.create(family=self.family, name='Alimentación', icon='food')
        self.salary = Category.objects.create(family=self.family, name='Sueldo', icon='salary')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.rows = [
            {'kind': 'expense', 'amount': '12.50', 'date': '2026-08-15', 'category': self.category.pk, 'description': 'Compra'},
            {'kind': 'income', 'amount': '1000', 'date': '2026-08-16', 'category': self.salary.pk, 'description': 'Sueldo'},
        ]

    def prepare(self, rows=None):
        return self.client.post('/api/assistant/movement-proposals/', {'movements': rows or self.rows}, format='json')

    def confirm(self, proposal, **data):
        return self.client.post(f'/api/assistant/movement-proposals/{proposal}/confirm/', data, format='json')

    def draft(self, text):
        return self.client.post('/api/assistant/movement-drafts/', {'text': text, 'year': 2026, 'month': 8}, format='json')


@override_settings(ASSISTANT_ENABLED=True, SECURE_SSL_REDIRECT=False)
class AssistantMovementTests(MovementFixtures, TestCase):
    def test_drafts_resolve_dynamic_categories_without_writing(self):
        response = self.draft('Gasté 12,50 en alimentación; Cobré 1000 de sueldo 2026-08-16')
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data['rows']
        self.assertEqual([(r['kind'], r['amount'], r['category']) for r in rows],
                         [('expense', '12.50', self.category.pk), ('income', '1000.00', self.salary.pk)])
        self.assertFalse(Expense.objects.exists())
        self.assertFalse(Income.objects.exists())
        self.assertFalse(Month.objects.exists())
        self.assertFalse(MovementProposal.objects.exists())

    def test_ambiguity_invalid_amounts_and_dates_require_review(self):
        for text in ('12 supermercado', 'Gasté 12 y 15 en alimentación', 'Gaste -12 en alimentación',
                     'Gaste 999999999999999999999999999999999999999999999999 en alimentación',
                     'Gaste 12 ayer en alimentación', 'Gaste 12 en alimentación 2026-99-99'):
            with self.subTest(text=text):
                response = self.draft(text)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data['rows'][0]['errors'])
        self.assertEqual(self.draft('\n'.join(['gasto 1'] * 21)).status_code, 400)

    def test_explicit_temporal_phrases_never_silently_use_selected_month(self):
        with patch('core.assistant.movements.timezone.localdate', return_value=date(2026, 11, 13)):
            today = self.draft('Gaste 12 hoy en alimentación').data['rows'][0]
            self.assertEqual(today['date'], '2026-11-13')
            self.assertTrue(today['errors'])
            for text in ('Gaste 12 el 15 de agosto en alimentación',
                         'Gaste 12 el mes pasado en alimentación',
                         'Gaste 12 el 15 en alimentación',
                         'Gaste 12 el 15/08/2026 en alimentación'):
                row = self.draft(text).data['rows'][0]
                self.assertIsNone(row['date'], text)
                self.assertTrue(row['errors'])

    def test_prepare_does_not_write_financial_rows_and_confirmation_is_idempotent(self):
        prepared = self.prepare()
        self.assertEqual(prepared.status_code, 201, prepared.data)
        self.assertFalse(Expense.objects.exists())
        self.assertFalse(Income.objects.exists())
        self.assertFalse(Month.objects.exists())
        first = self.confirm(prepared.data['id'], confirmed=True)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertTrue(first.data['created'])
        second = self.confirm(prepared.data['id'], confirmed=True)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.data['created'])
        self.assertEqual(first.data['movements'], second.data['movements'])
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(Expense.objects.get().payer, self.user)
        self.assertEqual(Income.objects.count(), 1)
        budget = self.client.get('/api/budget/?year=2026&month=8')
        self.assertEqual(str(budget.data['cash_balance']), '987.50')

    def test_confirmation_requires_literal_true_and_rejects_modified_payload(self):
        proposal = self.prepare().data['id']
        for data in ({}, {'confirmed': False}, {'confirmed': 'true'}, {'confirmed': 1},
                     {'confirmed': True, 'movements': self.rows}, {'confirmed': True, 'family': self.family.pk}):
            self.assertEqual(self.confirm(proposal, **data).status_code, 400)
        self.assertFalse(Expense.objects.exists())

    def test_expired_proposal_cannot_write(self):
        proposal = self.prepare().data['id']
        MovementProposal.objects.filter(pk=proposal).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.confirm(proposal, confirmed=True).status_code, 409)
        self.assertFalse(Expense.objects.exists())

    def test_closed_month_is_rechecked_on_confirm(self):
        proposal = self.prepare().data['id']
        Month.objects.create(family=self.family, year=2026, month=8, is_closed=True)
        self.assertEqual(self.confirm(proposal, confirmed=True).status_code, 400)
        self.assertFalse(Expense.objects.exists())
        self.assertFalse(Income.objects.exists())
        self.assertIsNone(MovementProposal.objects.get(pk=proposal).confirmed_at)
        self.assertEqual(self.prepare().status_code, 400)

    def test_actor_and_tenant_isolation(self):
        proposal = self.prepare().data['id']
        other = User.objects.create_user(username='other')
        self.client.force_authenticate(other)
        self.assertEqual(self.confirm(proposal, confirmed=True).status_code, 404)
        self.assertEqual(self.prepare().status_code, 400)
        other.profile.family = self.family
        other.profile.save()
        self.assertEqual(self.confirm(proposal, confirmed=True).status_code, 404)

    def test_unknown_fields_and_links_rejected(self):
        for field in ('family', 'user', 'income_plan', 'recurring_payment', 'planned_expense_plan', 'payer'):
            rows = [{**self.rows[0], field: 1}]
            self.assertEqual(self.prepare(rows).status_code, 400)
        self.assertEqual(self.client.post('/api/assistant/movement-proposals/',
            {'movements': self.rows, 'family': self.family.pk}, format='json').status_code, 400)
        self.assertFalse(MovementProposal.objects.exists())

    def test_category_is_rechecked_on_confirm(self):
        proposal = self.prepare().data['id']
        self.category.delete()
        self.assertEqual(self.confirm(proposal, confirmed=True).status_code, 400)
        self.assertFalse(Income.objects.exists())

    def test_batch_rolls_back_all_writes_if_later_row_fails(self):
        proposal = self.prepare().data['id']
        with patch('core.views.assistant_movement_view.IncomeViewSet.perform_create', side_effect=ValidationError('Unavailable')):
            self.assertEqual(self.confirm(proposal, confirmed=True).status_code, 400)
        self.assertFalse(Expense.objects.exists())
        self.assertFalse(Month.objects.exists())
        self.assertIsNone(MovementProposal.objects.get(pk=proposal).confirmed_at)

    def test_alias_learns_only_after_explicit_confirmation_and_is_family_scoped(self):
        rows = [{**self.rows[0], 'alias': 'Mercadó', 'learn_alias': True}]
        proposal = self.prepare(rows).data['id']
        self.assertFalse(FamilyCategoryAlias.objects.exists())
        self.assertEqual(self.confirm(proposal, confirmed=True).status_code, 200)
        self.assertEqual(FamilyCategoryAlias.objects.get().alias, 'mercado')
        self.assertEqual(self.draft('Gasto 15 en mercado').data['rows'][0]['category'], self.category.pk)
        other = User.objects.create_user(username='other-family')
        self.client.force_authenticate(other)
        self.assertIsNone(self.draft('Gasto 15 en mercado').data['rows'][0]['category'])

    def test_alias_without_opt_in_is_not_learned_and_conflicts_are_rejected(self):
        proposal = self.prepare([{**self.rows[0], 'alias': 'market'}]).data['id']
        self.confirm(proposal, confirmed=True)
        self.assertFalse(FamilyCategoryAlias.objects.exists())
        FamilyCategoryAlias.objects.create(family=self.family, alias='market', category=self.salary, learned_by=self.user)
        self.assertEqual(self.prepare([{**self.rows[0], 'alias': 'market', 'learn_alias': True}]).status_code, 400)

    @override_settings(ASSISTANT_ENABLED=False)
    def test_disabled_assistant_has_no_write_routes(self):
        self.assertEqual(self.prepare().status_code, 404)
        self.assertEqual(self.draft('gasto 15').status_code, 404)

    def test_session_csrf_required(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post('/api/assistant/movement-proposals/', {'movements': self.rows}, format='json').status_code, 403)


@override_settings(ASSISTANT_ENABLED=True, SECURE_SSL_REDIRECT=False)
class ConcurrentAssistantMovementTests(MovementFixtures, TransactionTestCase):
    def test_parallel_confirmations_create_batch_once(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL row locks required')
        proposal = self.prepare().data['id']
        barrier = Barrier(2)
        def confirm():
            client = APIClient()
            client.force_authenticate(User.objects.get(pk=self.user.pk))
            try:
                barrier.wait(timeout=10)
                response = client.post(f'/api/assistant/movement-proposals/{proposal}/confirm/', {'confirmed': True}, format='json')
                return response.status_code, response.data
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: confirm(), range(2)))
        self.assertEqual([status for status, _ in results], [200, 200], results)
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(Income.objects.count(), 1)
        self.assertEqual(sorted(result['created'] for _, result in results), [False, True])
