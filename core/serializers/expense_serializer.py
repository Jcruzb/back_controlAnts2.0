from rest_framework import serializers
from core.models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "id",
            "description",
            "amount",
            "category",
            "date",
            "month",
            "planned_expense",
            "recurring_payment",
            "is_recurring",
        ]
        read_only_fields = ("month",)

    def validate_category(self, value):
        # Permitir vacío o null (legacy / compatibilidad)
        if value in [None, ""]:
            return None
        return value