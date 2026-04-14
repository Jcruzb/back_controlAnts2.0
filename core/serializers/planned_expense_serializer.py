from django.shortcuts import get_object_or_404
from rest_framework import serializers

from core.models import PlannedExpense, Category, Month, Profile


class PlannedExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    spent_amount = serializers.SerializerMethodField()
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none())
    month = serializers.PrimaryKeyRelatedField(queryset=Month.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            profile = get_object_or_404(Profile, user=request.user)
            self.fields["category"].queryset = Category.objects.filter(family=profile.family)
            self.fields["month"].queryset = Month.objects.filter(family=profile.family)

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

    def validate(self, attrs):
        planned_amount = attrs.get("planned_amount", getattr(self.instance, "planned_amount", None))
        if planned_amount is None or planned_amount <= 0:
            raise serializers.ValidationError({"planned_amount": "planned_amount must be greater than 0"})
        return attrs
