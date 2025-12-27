from rest_framework import serializers
from core.models import RecurringPayment, Category


class RecurringPaymentSerializer(serializers.ModelSerializer):
    # Permitimos enviar y recibir la categoría como ID
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all()
    )

    due_day = serializers.IntegerField(min_value=1, max_value=31)

    class Meta:
        model = RecurringPayment
        fields = [
            "id",
            "name",
            "amount",
            "due_day",
            "category",
            "start_date",
            "end_date",
            "active",
        ]
        read_only_fields = (
            "id",
            "active",
        )