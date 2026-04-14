from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from core.models import PlannedExpensePlan, PlannedExpenseVersion, Profile
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
        profile = get_object_or_404(Profile, user=self.request.user)
        return PlannedExpensePlan.objects.filter(
            family=profile.family
        ).select_related(
            'family',
            'category',
            'start_month',
            'end_month',
            'created_by',
        ).prefetch_related('versions').order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        request = self.request
        profile = get_object_or_404(Profile, user=self.request.user)

        planned_amount = request.data.get("planned_amount")
        start_month = serializer.validated_data.get("start_month", instance.start_month)
        end_month = serializer.validated_data.get("end_month", instance.end_month)

        if start_month.is_closed or (end_month is not None and end_month.is_closed):
            raise ValidationError({"detail": "This month is closed and cannot be modified"})

        plan = serializer.save(family=profile.family)

        if planned_amount is not None:
            try:
                planned_amount = Decimal(str(planned_amount))
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError({"planned_amount": "planned_amount must be a number"})

            if planned_amount <= 0:
                raise ValidationError({"planned_amount": "planned_amount must be greater than 0"})

            last_version = (
                PlannedExpenseVersion.objects
                .filter(plan=plan)
                .order_by("-valid_from")
                .first()
            )

            if last_version and last_version.planned_amount != planned_amount:
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
