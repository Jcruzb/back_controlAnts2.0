from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from core.models import PlannedExpense
from core.serializers.planned_expense_serializer import PlannedExpenseSerializer
from core.serializers.recurringPayment_serializer import RecurringPaymentCompletionSerializer
from core.services.planned_payment_service import get_planned_payment_month_state
from core.permissions import IsFamilyAdminOrReadOnly


class PlannedExpenseViewSet(ModelViewSet):
    serializer_class = PlannedExpenseSerializer
    permission_classes = [IsAuthenticated, IsFamilyAdminOrReadOnly]
    family_member_actions = ("month_status",)

    def get_queryset(self):
        user = self.request.user
        family = user.profile.family
        return PlannedExpense.objects.filter(family=family).select_related(
            'month',
            'category',
            'created_by',
        )

    def perform_create(self, serializer):
        month_obj = serializer.validated_data["month"]
        if month_obj.is_closed:
            raise ValidationError({"detail": "This month is closed and cannot be modified"})

        serializer.save(
            family=self.request.user.profile.family,
            created_by=self.request.user
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        target_month = serializer.validated_data.get("month", instance.month)

        if instance.month.is_closed or target_month.is_closed:
            raise ValidationError({"detail": "This month is closed and cannot be modified"})

        serializer.save()

    def perform_destroy(self, instance):
        if instance.month.is_closed:
            raise ValidationError({"detail": "This month is closed and cannot be modified"})
        instance.delete()

    @action(detail=True, methods=["get", "patch"], url_path="month-status")
    def month_status(self, request, pk=None):
        planned_expense = self.get_object()
        year = request.query_params.get("year")
        month_number = request.query_params.get("month")

        try:
            year = int(year)
            month_number = int(month_number)
        except (TypeError, ValueError):
            raise ValidationError({"detail": "Query params year and month must be valid integers"})

        if (year, month_number) != (planned_expense.month.year, planned_expense.month.month):
            raise ValidationError({"detail": "Planned expense does not apply to the selected month"})

        occurrence, amounts = get_planned_payment_month_state(
            planned_expense=planned_expense,
            month=planned_expense.month,
        )

        if request.method == "PATCH":
            if planned_expense.month.is_closed:
                raise ValidationError({"detail": "This month is closed and cannot be modified"})
            input_serializer = RecurringPaymentCompletionSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            occurrence.is_completed = input_serializer.validated_data["is_completed"]
            occurrence.save(update_fields=["is_completed"])
            occurrence, amounts = get_planned_payment_month_state(
                planned_expense=planned_expense,
                month=planned_expense.month,
            )

        return Response(
            {
                "id": occurrence.id,
                "planned_expense": planned_expense.id,
                "planned_expense_plan": None,
                "month": planned_expense.month.id,
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
