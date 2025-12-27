from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from core.models import RecurringPayment, Profile
from core.serializers.recurringPayment_serializer import RecurringPaymentSerializer


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
        )

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)

        amount = serializer.validated_data.get("amount")
        if amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than 0"})

        start_date = serializer.validated_data.get("start_date")
        end_date = serializer.validated_data.get("end_date")

        if end_date is not None and end_date < start_date:
            raise ValidationError(
                {"end_date": "End date cannot be earlier than start date"}
            )

        serializer.save(
            family=profile.family
        )

    def perform_update(self, serializer):
        amount = serializer.validated_data.get("amount")
        if amount is not None and amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than 0"})

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