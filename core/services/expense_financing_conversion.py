"""Convert a paid movement into an initial financing payment without rewriting it."""
from calendar import monthrange
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from core.models import (Category, CreditAccount, Family, Month, FinancedPurchase,
    FinancingInstallment, FinancingPayment, RecurringPaymentOccurrence, PlannedExpenseOccurrence)
from core.services.recurring_payment_service import get_or_create_recurring_payment_occurrence
from core.services.planned_payment_service import get_or_create_planned_expense_occurrence
from core.views.financing_viewset import PurchaseSerializer


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({'non_field_errors': ['Unknown fields are not accepted']})
        return super().to_internal_value(data)


class ExpenseSnapshot(StrictInput):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    date = serializers.DateField()
    category = serializers.IntegerField(allow_null=True)
    payer = serializers.IntegerField(allow_null=True)
    description = serializers.CharField(allow_blank=True, trim_whitespace=False)
    month = serializers.IntegerField()
    planned_expense = serializers.IntegerField(allow_null=True)
    planned_expense_plan = serializers.IntegerField(allow_null=True)
    recurring_payment = serializers.IntegerField(allow_null=True)
    is_recurring = serializers.BooleanField()


class ConversionInput(StrictInput):
    confirmed = serializers.BooleanField()
    idempotency_key = serializers.UUIDField()
    name = serializers.CharField(max_length=100)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    credit_account = serializers.IntegerField(allow_null=True, default=None)
    category = serializers.IntegerField(required=False, allow_null=True)
    installment_count = serializers.IntegerField(min_value=0, max_value=360)
    first_due_date = serializers.DateField(allow_null=True)
    expected_expense = ExpenseSnapshot()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or data.get('confirmed') is not True:
            raise serializers.ValidationError({'confirmed': 'Explicit confirmed:true is required'})
        return super().to_internal_value(data)


def snapshot(expense):
    return {'amount': str(expense.amount), 'date': expense.date.isoformat(),
        'category': expense.category_id, 'payer': expense.payer_id,
        'description': expense.description, 'month': expense.month_id,
        'planned_expense': expense.planned_expense_id, 'planned_expense_plan': expense.planned_expense_plan_id,
        'recurring_payment': expense.recurring_payment_id, 'is_recurring': expense.is_recurring}


def check_occurrence(expense, month):
    if expense.recurring_payment_id:
        occurrence = get_or_create_recurring_payment_occurrence(recurring_payment=expense.recurring_payment, month=month)
        occurrence = RecurringPaymentOccurrence.objects.select_for_update().get(pk=occurrence.pk)
        if occurrence.is_completed:
            raise serializers.ValidationError('Reopen the recurring occurrence before conversion')
    if expense.planned_expense_id or expense.planned_expense_plan_id:
        occurrence = get_or_create_planned_expense_occurrence(month=month,
            planned_expense=expense.planned_expense, planned_expense_plan=expense.planned_expense_plan)
        occurrence = PlannedExpenseOccurrence.objects.select_for_update().get(pk=occurrence.pk)
        if occurrence.is_completed:
            raise serializers.ValidationError('Reopen the planned occurrence before conversion')


@transaction.atomic
def convert_expense(view, request, pk):
    serializer = ConversionInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    canonical = dict(serializer.data)
    family = request.user.profile.family
    Family.objects.select_for_update(no_key=True).get(pk=family.pk)
    expense = get_object_or_404(view.get_queryset().select_for_update(of=('self',)), pk=pk)
    existing = FinancedPurchase.objects.filter(family=family, idempotency_key=values['idempotency_key']).first()
    if existing:
        if existing.source_expense_id == expense.pk and existing.conversion_request == canonical:
            return Response(PurchaseSerializer(existing).data)
        return Response({'detail': 'Conversion key was already used with different values'}, status=409)
    if FinancingPayment.objects.filter(expense=expense).exists():
        return Response({'detail': 'This expense is already linked to financing'}, status=409)
    if canonical['expected_expense'] != snapshot(expense):
        return Response({'detail': 'Expense changed. Reload and review before confirming.'}, status=409)
    month = Month.objects.select_for_update().get(pk=expense.month_id)
    if month.is_closed:
        raise serializers.ValidationError('This month is closed and cannot be modified')
    check_occurrence(expense, month)
    if expense.amount <= 0:
        raise serializers.ValidationError({'amount': 'Original payment must be positive'})
    category_id = values.get('category') or expense.category_id
    if expense.category_id and category_id != expense.category_id:
        raise serializers.ValidationError({'category': 'Original category cannot be changed'})
    if category_id is None:
        raise serializers.ValidationError({'category': 'Choose a category for the purchase; original expense is preserved'})
    category = get_object_or_404(Category, pk=category_id, family=family)
    card = None
    if values['credit_account'] is not None:
        card = get_object_or_404(CreditAccount, pk=values['credit_account'], family=family)
    remaining = values['total_amount'] - expense.amount
    count, first = values['installment_count'], values['first_due_date']
    if remaining < 0:
        raise serializers.ValidationError({'total_amount': 'Total cannot be less than the payment already made'})
    if remaining == 0:
        if count != 0 or first is not None:
            raise serializers.ValidationError('Fully paid purchases require zero future installments and no first due date')
    else:
        if count < 1 or first is None or first <= expense.date:
            raise serializers.ValidationError('Remaining debt requires installments starting after the original payment date')
        if remaining * 100 < count:
            raise serializers.ValidationError('Every remaining installment must be at least one cent')
        if (first.year * 12 + first.month - 1 + count - 1) // 12 > 9999:
            raise serializers.ValidationError('Schedule exceeds supported dates')
    purchase = FinancedPurchase.objects.create(family=family, idempotency_key=values['idempotency_key'],
        name=values['name'], category=category, credit_account=card, purchase_date=expense.date,
        total_amount=values['total_amount'], installment_count=count, first_due_date=first,
        source_expense=expense, conversion_request=canonical)
    initial = FinancingInstallment.objects.create(purchase=purchase, number=0, due_date=expense.date, amount=expense.amount)
    FinancingPayment.objects.create(installment=initial, expense=expense, idempotency_key=values['idempotency_key'])
    if count:
        base, remainder = divmod(int(remaining * 100), count)
        rows = []
        for index in range(count):
            year, zero_month = divmod(first.year * 12 + first.month - 1 + index, 12)
            due = date(year, zero_month + 1, min(first.day, monthrange(year, zero_month + 1)[1]))
            rows.append(FinancingInstallment(purchase=purchase, number=index + 1, due_date=due,
                amount=Decimal(base + (remainder if index == count - 1 else 0)) / 100))
        FinancingInstallment.objects.bulk_create(rows)
    return Response(PurchaseSerializer(purchase).data, status=201)
