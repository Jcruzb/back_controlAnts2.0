from calendar import monthrange
from datetime import date
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework import serializers, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.models import CreditAccount, FinancedPurchase, FinancingInstallment, FinancingPayment, Expense, Month, Profile, Family
from core.permissions import IsFamilyAdminOrReadOnly


class CreditAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditAccount
        fields = ['id', 'name']


class PurchaseSerializer(serializers.ModelSerializer):
    idempotency_key = serializers.UUIDField(write_only=True, required=True)
    installments = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    outstanding_amount = serializers.SerializerMethodField()
    class Meta:
        model = FinancedPurchase
        fields = ['id', 'idempotency_key', 'name', 'category', 'credit_account', 'purchase_date', 'total_amount', 'installment_count', 'first_due_date', 'installments', 'paid_amount', 'outstanding_amount']
        extra_kwargs = {'total_amount': {'min_value': Decimal('0.01')}, 'installment_count': {'min_value': 1, 'max_value': 360}}
    def get_installments(self, obj):
        result = []
        for row in obj.installments.all():
            paid = sum((p.expense.amount for p in row.payments.all()), Decimal('0'))
            result.append({'id': row.id, 'number': row.number, 'due_date': row.due_date, 'amount': str(row.amount), 'paid_amount': str(paid), 'pending_amount': str(row.amount - paid)})
        return result
    def get_paid_amount(self, obj):
        return str(sum((Decimal(row['paid_amount']) for row in self.get_installments(obj)), Decimal('0')))
    def get_outstanding_amount(self, obj):
        return str(obj.total_amount - Decimal(self.get_paid_amount(obj)))
    def validate(self, attrs):
        family = self.context['request'].user.profile.family
        if attrs['category'].family_id != family.id:
            raise ValidationError({'category': 'Category does not belong to your family'})
        account = attrs.get('credit_account')
        if account and account.family_id != family.id:
            raise ValidationError({'credit_account': 'Account does not belong to your family'})
        if attrs['first_due_date'] < attrs['purchase_date']:
            raise ValidationError({'first_due_date': 'First installment cannot precede purchase'})
        if attrs['total_amount'] * 100 < attrs['installment_count']:
            raise ValidationError({'total_amount': 'Every installment must be at least one cent'})
        end_month = attrs['first_due_date'].year * 12 + attrs['first_due_date'].month - 1 + attrs['installment_count'] - 1
        if end_month // 12 > 9999:
            raise ValidationError({'first_due_date': 'Schedule exceeds supported dates'})
        return attrs


class FamilyCreateListViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, IsFamilyAdminOrReadOnly]
    pagination_class = None
    def get_queryset(self):
        return self.queryset.filter(family=self.request.user.profile.family)
    def perform_create(self, serializer):
        serializer.save(family=self.request.user.profile.family)


class CreditAccountViewSet(FamilyCreateListViewSet):
    queryset = CreditAccount.objects.order_by('id')
    serializer_class = CreditAccountSerializer


class FinancedPurchaseViewSet(FamilyCreateListViewSet):
    queryset = FinancedPurchase.objects.prefetch_related('installments__payments__expense').order_by('-id')
    serializer_class = PurchaseSerializer
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        family = request.user.profile.family
        # Serialize same-family creates before checking the key: there is no
        # purchase row to lock for the first request. The unique constraint is
        # an additional database guard, including callers outside this view.
        Family.objects.select_for_update().get(pk=family.pk)
        values = serializer.validated_data
        existing = self.get_queryset().filter(idempotency_key=values['idempotency_key']).first()
        if existing is not None:
            fields = ('name', 'category', 'credit_account', 'purchase_date', 'total_amount', 'installment_count', 'first_due_date')
            if any(getattr(existing, field) != values.get(field) for field in fields):
                return Response({'detail': 'This purchase key was already used with different values'}, status=409)
            return Response(self.get_serializer(existing).data, status=200)
        self.perform_create(serializer)
        return Response(serializer.data, status=201, headers=self.get_success_headers(serializer.data))

    @transaction.atomic
    def perform_create(self, serializer):
        family = self.request.user.profile.family
        purchase_date = serializer.validated_data['purchase_date']
        month, _ = Month.objects.get_or_create(family=family, year=purchase_date.year, month=purchase_date.month)
        month = Month.objects.select_for_update().get(pk=month.pk)
        if month.is_closed:
            raise ValidationError('Purchase month is closed')
        purchase = serializer.save(family=family)
        cents = int(purchase.total_amount * 100)
        base, remainder = divmod(cents, purchase.installment_count)
        start = purchase.first_due_date
        rows = []
        for index in range(purchase.installment_count):
            absolute = start.year * 12 + start.month - 1 + index
            year, zero_month = divmod(absolute, 12)
            month_number = zero_month + 1
            due = date(year, month_number, min(start.day, monthrange(year, month_number)[1]))
            amount = Decimal(base + (remainder if index == purchase.installment_count - 1 else 0)) / 100
            rows.append(FinancingInstallment(purchase=purchase, number=index + 1, due_date=due, amount=amount))
        FinancingInstallment.objects.bulk_create(rows)


class PaymentInput(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    date = serializers.DateField()
    payer = serializers.IntegerField(required=False)
    idempotency_key = serializers.UUIDField()


class FinancingInstallmentViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = FinancingInstallment.objects.all()
    http_method_names = ['post', 'options']
    @action(detail=True, methods=['post'], url_path='payments')
    @transaction.atomic
    def payments(self, request, pk=None):
        profile = get_object_or_404(Profile, user=request.user)
        row = get_object_or_404(FinancingInstallment.objects.select_for_update(), pk=pk, purchase__family=profile.family)
        data = PaymentInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        payer_id = values.get('payer', request.user.id)
        get_object_or_404(Profile, family=profile.family, user_id=payer_id, user__is_active=True)
        existing = row.payments.filter(idempotency_key=values['idempotency_key']).select_related('expense').first()
        if existing:
            expense = existing.expense
            if expense.amount != values['amount'] or expense.date != values['date'] or expense.payer_id != payer_id:
                return Response({'detail': 'This payment key was already used with different values'}, status=409)
            return Response({'expense_id': expense.id, 'created': False})
        paid = row.payments.aggregate(total=Sum('expense__amount'))['total'] or Decimal('0')
        if paid + values['amount'] > row.amount:
            raise ValidationError({'amount': 'Payment exceeds outstanding installment amount'})
        paid_date = values['date']
        if paid_date < row.purchase.purchase_date:
            raise ValidationError({'date': 'Payment cannot precede purchase'})
        month, _ = Month.objects.get_or_create(family=profile.family, year=paid_date.year, month=paid_date.month)
        month = Month.objects.select_for_update().get(pk=month.pk)
        if month.is_closed:
            raise ValidationError('Payment month is closed')
        expense = Expense.objects.create(user=request.user, payer_id=payer_id, month=month, category=row.purchase.category, amount=values['amount'], date=paid_date, description=f'{row.purchase.name} · cuota {row.number}')
        FinancingPayment.objects.create(installment=row, expense=expense, idempotency_key=values['idempotency_key'])
        return Response({'expense_id': expense.id, 'created': True}, status=201)
