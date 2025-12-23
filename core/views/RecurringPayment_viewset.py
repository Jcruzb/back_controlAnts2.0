from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from core.models import RecurringPayment, Profile, Month
from core.serializers.recurringPayment_serializer import RecurringPaymentSerializer


class RecurringPaymentViewSet(ModelViewSet):
    serializer_class = RecurringPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)

        queryset = RecurringPayment.objects.filter(
            family=profile.family
        )

        return queryset

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)

        amount = serializer.validated_data.get('amount')
        if amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than 0'})

        serializer.save(
            user=self.request.user,
            family=profile.family,
        )

    def perform_update(self, serializer):
        amount = serializer.validated_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than 0'})

        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()