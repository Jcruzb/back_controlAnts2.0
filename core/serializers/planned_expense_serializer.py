from rest_framework import serializers
from core.models import PlannedExpense


class PlannedExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    spent_amount = serializers.SerializerMethodField()

    class Meta:
        model = PlannedExpense
        fields = [
            'id',
            'month',
            'family',
            'category',
            'category_name',
            'name',
            'planned_amount',
            'spent_amount',
            'created_by',
            'created_at',
        ]
        read_only_fields = ['family', 'created_by', 'created_at', 'spent_amount']

    def get_spent_amount(self, obj):
        return sum(exp.amount for exp in obj.expenses.all())