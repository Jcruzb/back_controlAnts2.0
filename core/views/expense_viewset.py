from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from core.models import Expense, Profile, Month
from core.serializers.expense_serializer import ExpenseSerializer


class ExpenseViewSet(ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)

        queryset = Expense.objects.filter(
            month__family=profile.family
        ).select_related(
            'category',
            'month',
            'user',
            'payer',
            'payer__profile',
            'planned_expense',
            'recurring_payment',
        )

        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        payer = self.request.query_params.get('payer')

        if year and month:
            try:
                year_int = int(year)
                month_int = int(month)
            except (TypeError, ValueError):
                raise ValidationError({'detail': 'Query params year and month must be integers'})

            queryset = queryset.filter(
                month__year=year_int,
                month__month=month_int
            )

        if payer:
            try:
                payer_int = int(payer)
            except (TypeError, ValueError):
                raise ValidationError({'detail': 'Query param payer must be an integer'})

            queryset = queryset.filter(payer_id=payer_int)

        return queryset

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)

        expense_date = serializer.validated_data.get('date')
        if not expense_date:
            raise ValidationError({'date': 'Date is required'})

        month_obj, _ = Month.objects.get_or_create(
            family=profile.family,
            year=expense_date.year,
            month=expense_date.month,
            defaults={'is_closed': False},
        )

        if month_obj.is_closed:
            raise ValidationError('This month is closed and cannot be modified')

        amount = serializer.validated_data.get('amount')
        if amount is None or amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than 0'})

        save_kwargs = {
            'user': self.request.user,
            'month': month_obj,
        }
        if 'payer' not in serializer.validated_data:
            save_kwargs['payer'] = self.request.user

        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        instance = self.get_object()

        # If the existing month is closed, do not allow any modification
        if instance.month.is_closed:
            raise ValidationError('This month is closed and cannot be modified')

        # Validate amount if provided
        amount = serializer.validated_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than 0'})

        # If date is being changed, ensure month is aligned with the new date
        new_date = serializer.validated_data.get('date')
        if new_date is not None:
            profile = get_object_or_404(Profile, user=self.request.user)

            month_obj, _ = Month.objects.get_or_create(
                family=profile.family,
                year=new_date.year,
                month=new_date.month,
                defaults={'is_closed': False},
            )

            if month_obj.is_closed:
                raise ValidationError('This month is closed and cannot be modified')

            serializer.save(month=month_obj)
            return

        serializer.save()

    def perform_destroy(self, instance):
        # Block deletes for closed months
        if instance.month.is_closed:
            raise ValidationError('This month is closed and cannot be modified')

        instance.delete()
        
