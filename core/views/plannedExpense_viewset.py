from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from core.models import PlannedExpense
from core.serializers.planned_expense_serializer import PlannedExpenseSerializer


class PlannedExpenseViewSet(ModelViewSet):
    serializer_class = PlannedExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        family = user.profile.family
        return PlannedExpense.objects.filter(family=family)

    def perform_create(self, serializer):
        serializer.save(
            family=self.request.user.profile.family,
            created_by=self.request.user
        )