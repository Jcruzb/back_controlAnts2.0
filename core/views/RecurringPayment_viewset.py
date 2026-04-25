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
    RecurringPaymentPaymentsSerializer,
    RecurringPaymentSerializer,
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
