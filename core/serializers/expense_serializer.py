from rest_framework import serializers
from django.shortcuts import get_object_or_404

from core.models import Expense, Category, PlannedExpense, Profile, RecurringPayment


class ExpenseSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none())
    planned_expense = serializers.PrimaryKeyRelatedField(
        queryset=PlannedExpense.objects.none(),
        required=False,
        allow_null=True,
    )
    recurring_payment = serializers.PrimaryKeyRelatedField(
        queryset=RecurringPayment.objects.none(),
        required=False,
        allow_null=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            profile = get_object_or_404(Profile, user=request.user)
            self.fields["category"].queryset = Category.objects.filter(family=profile.family)
            self.fields["planned_expense"].queryset = PlannedExpense.objects.filter(family=profile.family)
            self.fields["recurring_payment"].queryset = RecurringPayment.objects.filter(family=profile.family)

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

    def validate(self, attrs):
        category = attrs.get("category") or getattr(self.instance, "category", None)
        planned_expense = attrs.get("planned_expense", getattr(self.instance, "planned_expense", None))
        recurring_payment = attrs.get("recurring_payment", getattr(self.instance, "recurring_payment", None))

        if category is None:
            raise serializers.ValidationError({"category": "Category is required"})

        if planned_expense is not None and planned_expense.category_id != category.id:
            raise serializers.ValidationError(
                {"planned_expense": "Planned expense category must match the expense category"}
            )

        if recurring_payment is not None and recurring_payment.category_id != category.id:
            raise serializers.ValidationError(
                {"recurring_payment": "Recurring payment category must match the expense category"}
            )

        return attrs
