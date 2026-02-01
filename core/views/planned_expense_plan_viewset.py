

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from core.models import PlannedExpensePlan, PlannedExpenseVersion
from core.serializers.planned_expense_plan_serializer import (
    PlannedExpensePlanSerializer,
)


class PlannedExpensePlanViewSet(ModelViewSet):
    """
    ViewSet for PlannedExpensePlan (new planning system).

    - ONE_MONTH plans are created for a single month.
    - ONGOING plans remain active until deactivated.
    - Editing a plan creates a new PlannedExpenseVersion (history preserved).
    """

    serializer_class = PlannedExpensePlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Restrict plans to the authenticated user.
        """
        return PlannedExpensePlan.objects.filter(
            created_by=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        """
        Creation is handled entirely by the serializer.
        Family and created_by are injected there.
        """
        serializer.save()

    def perform_update(self, serializer):
        """
        Updating a plan DOES NOT overwrite history.
        A new PlannedExpenseVersion is created if planned_amount changes.
        """
        instance = self.get_object()
        request = self.request

        planned_amount = request.data.get("planned_amount")

        # Save basic plan fields (name, active, end_month, etc.)
        plan = serializer.save()

        if planned_amount is not None:
            # Close previous version if exists
            last_version = (
                PlannedExpenseVersion.objects
                .filter(plan=plan)
                .order_by("-valid_from")
                .first()
            )

            if last_version:
                last_version.valid_to = plan.start_month
                last_version.save()

            # Create new version starting from the plan start_month
            PlannedExpenseVersion.objects.create(
                plan=plan,
                planned_amount=planned_amount,
                valid_from=plan.start_month,
            )

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """
        Deactivate an ongoing plan.
        """
        plan = self.get_object()
        plan.active = False
        plan.save()
        return Response(
            {"status": "deactivated"},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        """
        Reactivate a previously deactivated plan.
        """
        plan = self.get_object()
        plan.active = True
        plan.save()
        return Response(
            {"status": "reactivated"},
            status=status.HTTP_200_OK
        )