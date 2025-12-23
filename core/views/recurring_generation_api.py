import calendar
from datetime import date

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from core.models import RecurringPayment, Expense, Month, Profile


class GenerateRecurringExpensesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = get_object_or_404(Profile, user=request.user)

        today = date.today()
        year = today.year
        month_num = today.month

        month_obj, _ = Month.objects.get_or_create(
            family=profile.family,
            year=year,
            month=month_num,
            defaults={'is_closed': False},
        )

        if month_obj.is_closed:
            raise ValidationError('This month is closed and cannot generate expenses')

        created = 0
        skipped = 0

        recurring_payments = RecurringPayment.objects.filter(
            family=profile.family,
            active=True,
        )

        for rp in recurring_payments:
            exists = Expense.objects.filter(
                month=month_obj,
                recurring_payment=rp,
            ).exists()

            if exists:
                skipped += 1
                continue

            last_day = calendar.monthrange(year, month_num)[1]
            day = min(rp.day_of_month, last_day)
            expense_date = date(year, month_num, day)
            Expense.objects.create(
                user=request.user,
                month=month_obj,
                recurring_payment=rp,
                amount=rp.amount,
                category=rp.category,
                date=expense_date,
                is_recurring=True,
            )
            created += 1

        return Response({
            'month': f'{year}-{month_num}',
            'created': created,
            'skipped': skipped,
        })