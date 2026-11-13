from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from core.models import Expense, Profile, Month
from core.serializers.expense_serializer import ExpenseSerializer
from core.services.recurring_payment_service import (
    get_or_create_recurring_payment_occurrence,
)
from core.services.planned_payment_service import (
    get_or_create_planned_expense_occurrence,
)


class ExpenseViewSet(ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def paginate_queryset(self, queryset):
        if self.request.query_params.get('year') and self.request.query_params.get('month'):
            return None
        return super().paginate_queryset(queryset)

    def _ensure_recurring_occurrence_is_open(self, *, recurring_payment, month):
        if recurring_payment is None:
            return

        occurrence = get_or_create_recurring_payment_occurrence(
            recurring_payment=recurring_payment,
            month=month,
        )
        if occurrence.is_completed:
            raise ValidationError(
                {
                    'recurring_payment': (
                        'This recurring payment is completed for the selected month. '
                        'Reopen it before changing its movements.'
                    )
                }
            )

    def _ensure_planned_occurrence_is_open(
        self, *, planned_expense, planned_expense_plan, month
    ):
        if planned_expense is None and planned_expense_plan is None:
            return

        occurrence = get_or_create_planned_expense_occurrence(
            planned_expense=planned_expense,
            planned_expense_plan=planned_expense_plan,
            month=month,
        )
        if occurrence.is_completed:
            raise ValidationError(
                {
                    "planned_payment": (
                        "This planned payment is completed for the selected month. "
                        "Reopen it before changing its movements."
                    )
                }
            )

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
            'planned_expense_plan',
            'recurring_payment',
        ).order_by('-date', '-created_at', '-id')

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

        self._ensure_recurring_occurrence_is_open(
            recurring_payment=serializer.validated_data.get('recurring_payment'),
            month=month_obj,
        )
        self._ensure_planned_occurrence_is_open(
            planned_expense=serializer.validated_data.get("planned_expense"),
            planned_expense_plan=serializer.validated_data.get("planned_expense_plan"),
            month=month_obj,
        )

        save_kwargs = {
            'user': self.request.user,
            'month': month_obj,
        }
        if 'payer' not in serializer.validated_data:
            save_kwargs['payer'] = self.request.user

        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        instance = self.get_object()
        if hasattr(instance, "financing_payment"):
            raise ValidationError("Financing payments cannot be edited through expenses")

        # If the existing month is closed, do not allow any modification
        if instance.month.is_closed:
            raise ValidationError('This month is closed and cannot be modified')

        self._ensure_recurring_occurrence_is_open(
            recurring_payment=instance.recurring_payment,
            month=instance.month,
        )
        self._ensure_planned_occurrence_is_open(
            planned_expense=instance.planned_expense,
            planned_expense_plan=instance.planned_expense_plan,
            month=instance.month,
        )

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

            self._ensure_recurring_occurrence_is_open(
                recurring_payment=serializer.validated_data.get(
                    'recurring_payment', instance.recurring_payment
                ),
                month=month_obj,
            )
            self._ensure_planned_occurrence_is_open(
                planned_expense=serializer.validated_data.get(
                    "planned_expense", instance.planned_expense
                ),
                planned_expense_plan=serializer.validated_data.get(
                    "planned_expense_plan", instance.planned_expense_plan
                ),
                month=month_obj,
            )

            serializer.save(month=month_obj)
            return

        self._ensure_recurring_occurrence_is_open(
            recurring_payment=serializer.validated_data.get(
                'recurring_payment', instance.recurring_payment
            ),
            month=instance.month,
        )
        self._ensure_planned_occurrence_is_open(
            planned_expense=serializer.validated_data.get(
                "planned_expense", instance.planned_expense
            ),
            planned_expense_plan=serializer.validated_data.get(
                "planned_expense_plan", instance.planned_expense_plan
            ),
            month=instance.month,
        )

        serializer.save()

    def perform_destroy(self, instance):
        if hasattr(instance, "financing_payment"):
            raise ValidationError("Financing payments cannot be deleted through expenses")
        # Block deletes for closed months
        if instance.month.is_closed:
            raise ValidationError('This month is closed and cannot be modified')

        self._ensure_recurring_occurrence_is_open(
            recurring_payment=instance.recurring_payment,
            month=instance.month,
        )
        self._ensure_planned_occurrence_is_open(
            planned_expense=instance.planned_expense,
            planned_expense_plan=instance.planned_expense_plan,
            month=instance.month,
        )

        instance.delete()
        
