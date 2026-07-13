from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError

from core.models import Month, PlannedExpensePlan, PlannedExpenseVersion, Profile
from core.serializers.planned_expense_plan_serializer import (
    PlannedExpensePlanSerializer,
)
from core.serializers.recurringPayment_serializer import RecurringPaymentCompletionSerializer
from core.services.planned_payment_service import get_planned_payment_month_state
from core.permissions import IsFamilyAdminOrReadOnly


class PlannedExpensePlanViewSet(ModelViewSet):
    """
    ViewSet for PlannedExpensePlan (new planning system).

    - ONE_MONTH plans are created for a single month.
    - ONGOING plans remain active until deactivated.
    - Editing a plan creates a new PlannedExpenseVersion (history preserved).
    """

    serializer_class = PlannedExpensePlanSerializer
    permission_classes = [IsAuthenticated, IsFamilyAdminOrReadOnly]
    family_member_actions = ("month_status",)

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

    @transaction.atomic
    def perform_update(self, serializer):
        instance = self.get_object()
        request = self.request
        profile = get_object_or_404(Profile, user=self.request.user)

        planned_amount = request.data.get("planned_amount")
        effective_month = serializer.validated_data.pop("effective_month", None)
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

            if effective_month is None:
                raise ValidationError({"effective_month": "effective_month is required when planned_amount changes"})
            if (effective_month.year, effective_month.month) < (plan.start_month.year, plan.start_month.month):
                raise ValidationError({"effective_month": "effective_month cannot be before the plan start"})
            if effective_month.is_closed:
                raise ValidationError({"detail": "This month is closed and cannot be modified"})

            versions = list(
                PlannedExpenseVersion.objects.filter(plan=plan)
                .select_related("valid_from", "valid_to")
                .order_by("valid_from__year", "valid_from__month", "created_at")
            )
            current = next(
                (
                    version for version in reversed(versions)
                    if (version.valid_from.year, version.valid_from.month)
                    <= (effective_month.year, effective_month.month)
                    and (
                        version.valid_to is None
                        or (version.valid_to.year, version.valid_to.month)
                        >= (effective_month.year, effective_month.month)
                    )
                ),
                None,
            )
            same_start = next(
                (version for version in versions if version.valid_from_id == effective_month.id),
                None,
            )
            future = next(
                (
                    version for version in versions
                    if (version.valid_from.year, version.valid_from.month)
                    > (effective_month.year, effective_month.month)
                ),
                None,
            )

            if current is not None and same_start is None and current.planned_amount == planned_amount:
                return

            previous_year = effective_month.year if effective_month.month > 1 else effective_month.year - 1
            previous_number = effective_month.month - 1 if effective_month.month > 1 else 12
            previous_month, _ = type(effective_month).objects.get_or_create(
                family=profile.family, year=previous_year, month=previous_number
            )
            future_previous = None
            if future is not None:
                future_year = future.valid_from.year if future.valid_from.month > 1 else future.valid_from.year - 1
                future_number = future.valid_from.month - 1 if future.valid_from.month > 1 else 12
                future_previous, _ = type(effective_month).objects.get_or_create(
                    family=profile.family, year=future_year, month=future_number
                )

            for version in versions:
                starts_before = (version.valid_from.year, version.valid_from.month) < (
                    effective_month.year, effective_month.month
                )
                reaches_effective = version.valid_to is None or (
                    version.valid_to.year, version.valid_to.month
                ) >= (effective_month.year, effective_month.month)
                if starts_before and reaches_effective:
                    version.valid_to = previous_month
                    version.save(update_fields=["valid_to"])

            if same_start is not None:
                same_start.planned_amount = planned_amount
                same_start.valid_to = future_previous
                same_start.save(update_fields=["planned_amount", "valid_to"])
            else:
                PlannedExpenseVersion.objects.create(
                    plan=plan,
                    planned_amount=planned_amount,
                    valid_from=effective_month,
                    valid_to=future_previous,
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

    @action(detail=True, methods=["get", "patch"], url_path="month-status")
    def month_status(self, request, pk=None):
        plan = self.get_object()
        year = request.query_params.get("year")
        month_number = request.query_params.get("month")

        try:
            year = int(year)
            month_number = int(month_number)
            if year < 1 or year > 9999 or month_number < 1 or month_number > 12:
                raise ValueError
        except (TypeError, ValueError):
            raise ValidationError({"detail": "Query params year and month must be valid integers"})

        profile = get_object_or_404(Profile, user=request.user)
        month_obj, _ = Month.objects.get_or_create(
            family=profile.family,
            year=year,
            month=month_number,
            defaults={"is_closed": False},
        )

        try:
            occurrence, amounts = get_planned_payment_month_state(
                planned_expense_plan=plan,
                month=month_obj,
            )
        except ValueError as error:
            raise ValidationError({"detail": str(error)})

        if request.method == "PATCH":
            if month_obj.is_closed:
                raise ValidationError({"detail": "This month is closed and cannot be modified"})
            input_serializer = RecurringPaymentCompletionSerializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            occurrence.is_completed = input_serializer.validated_data["is_completed"]
            occurrence.save(update_fields=["is_completed"])
            occurrence, amounts = get_planned_payment_month_state(
                planned_expense_plan=plan,
                month=month_obj,
            )

        return Response(
            {
                "id": occurrence.id,
                "planned_expense": None,
                "planned_expense_plan": plan.id,
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
