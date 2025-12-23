from datetime import date

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
        )

        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')

        if year and month:
            queryset = queryset.filter(
                month__year=year,
                month__month=month
            )

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
        if amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than 0'})

        serializer.save(
            user=self.request.user,
            month=month_obj,
        )