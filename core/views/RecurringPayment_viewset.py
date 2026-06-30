import calendar
from datetime import date

from django.db.models import Prefetch
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from core.models import Expense, RecurringPayment, Profile
from core.serializers.recurringPayment_serializer import (
    RecurringPaymentCompletionSerializer,
    RecurringPaymentPaymentsSerializer,
    RecurringPaymentSerializer,
)
from core.models import Month
from core.services.recurring_payment_service import (
    get_recurring_payment_month_state,
)


class RecurringPaymentViewSet(ModelViewSet):
    """
    ViewSet para gestionar Gastos fijos (RecurringPayment).

    - Define compromisos mensuales
    - NO registra pagos
    - Ownership por family
    - DELETE = desactivación (soft delete)
    """
    serializer_class = RecurringPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)
        return RecurringPayment.objects.filter(
            family=profile.family
        ).select_related('category', 'payer', 'payer__profile').order_by('name')

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)

        amount = serializer.validated_data.get("amount")
        if amount is None or amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than 0"})

        start_date = serializer.validated_data.get("start_date")
        end_date = serializer.validated_data.get("end_date")

        if end_date is not None and end_date < start_date:
            raise ValidationError(
                {"end_date": "End date cannot be earlier than start date"}
            )

        save_kwargs = {'family': profile.family}
        if 'payer' not in serializer.validated_data:
            save_kwargs['payer'] = self.request.user

        serializer.save(**save_kwargs)

    def perform_update(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)
        amount = serializer.validated_data.get("amount")
        if amount is not None and amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than 0"})

        category = serializer.validated_data.get("category")
        if category is not None and category.family_id != profile.family_id:
            raise ValidationError({"category": "Category does not belong to your family"})

        end_date = serializer.validated_data.get("end_date")
        if end_date is not None:
            instance = self.get_object()
            start_date = serializer.validated_data.get(
                "start_date", instance.start_date
            )
            if end_date < start_date:
                raise ValidationError(
                    {"end_date": "End date cannot be earlier than start date"}
                )

        serializer.save()

    def perform_destroy(self, instance):
        # Soft delete: un gasto fijo desactivado no afecta meses futuros
        instance.active = False
        instance.save()
        
    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        recurring = self.get_object()

        if recurring.active:
            return Response(
                {"detail": "Recurring payment is already active"},
                status=status.HTTP_400_BAD_REQUEST
            )

        recurring.active = True
        recurring.save()

        serializer = self.get_serializer(recurring)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def payments(self, request, pk=None):
        profile = get_object_or_404(Profile, user=request.user)
        payments_qs = (
            Expense.objects.filter(month__family=profile.family)
            .select_related(
                "month",
                "category",
                "payer",
                "payer__profile",
                "planned_expense",
                "recurring_payment",
            )
            .order_by("-date", "-created_at")
        )
        recurring = get_object_or_404(
            self.get_queryset().prefetch_related(
                Prefetch(
                    "generated_expenses",
                    queryset=payments_qs,
                    to_attr="prefetched_generated_expenses",
                )
            ),
            pk=pk,
        )
        serializer = RecurringPaymentPaymentsSerializer(recurring, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get", "patch"], url_path="month-status")
    def month_status(self, request, pk=None):
        recurring = self.get_object()
        year = request.query_params.get("year")
        month_number = request.query_params.get("month")

        if year is None or month_number is None:
            raise ValidationError({"detail": "Query params year and month are required"})

        try:
            year = int(year)
            month_number = int(month_number)
            if year < 1 or year > 9999:
                raise ValueError
            last_day = calendar.monthrange(year, month_number)[1]
        except (TypeError, ValueError):
            raise ValidationError({"detail": "Query params year and month must be valid integers"})

        month_start = date(year, month_number, 1)
        month_end = date(year, month_number, last_day)
        if recurring.start_date > month_end or (
            recurring.end_date is not None and recurring.end_date < month_start
        ):
            raise ValidationError(
                {"detail": "Recurring payment does not apply to the selected month"}
            )

        profile = get_object_or_404(Profile, user=request.user)
        month_obj, _ = Month.objects.get_or_create(
            family=profile.family,
            year=year,
            month=month_number,
            defaults={"is_closed": False},
        )

        occurrence, amounts = get_recurring_payment_month_state(
            recurring_payment=recurring,
            month=month_obj,
        )

        if request.method == "PATCH":
            if month_obj.is_closed:
                raise ValidationError(
                    {"detail": "This month is closed and cannot be modified"}
                )

            input_serializer = RecurringPaymentCompletionSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            occurrence.is_completed = input_serializer.validated_data["is_completed"]
            occurrence.save(update_fields=["is_completed"])
            occurrence, amounts = get_recurring_payment_month_state(
                recurring_payment=recurring,
                month=month_obj,
            )

        return Response(
            {
                "id": occurrence.id,
                "recurring_payment": recurring.id,
                "month": month_obj.id,
                "year": year,
                "month_number": month_number,
                "planned_amount": amounts.planned_amount,
                "paid_amount": amounts.paid_amount,
                "pending_amount": amounts.pending_amount,
                "difference_amount": amounts.difference_amount,
                "is_completed": amounts.is_completed,
                "status": amounts.payment_status,
                "payment_status": amounts.payment_status,
            },
            status=status.HTTP_200_OK,
        )
