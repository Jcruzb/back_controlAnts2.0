from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from core.models import PlannedExpense
from core.serializers.planned_expense_serializer import PlannedExpenseSerializer


class PlannedExpenseViewSet(ModelViewSet):
    serializer_class = PlannedExpenseSerializer
    permission_classes = [IsAuthenticated]

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
