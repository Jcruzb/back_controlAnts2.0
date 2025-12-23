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
            "is_recurring",
        ]

    def validate_category(self, value):
        # Permitir vacío o null
        if value in [None, ""]:
            return ""
        return value