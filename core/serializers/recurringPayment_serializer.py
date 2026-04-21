from django.shortcuts import get_object_or_404
from rest_framework import serializers

from core.models import RecurringPayment, Category, Profile
from core.serializers.expense_serializer import ExpenseSerializer


class RecurringPaymentSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.none()
    )

    due_day = serializers.IntegerField(min_value=1, max_value=31)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            profile = get_object_or_404(Profile, user=request.user)
            self.fields["category"].queryset = Category.objects.filter(family=profile.family)

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


class RecurringPaymentPaymentsSerializer(RecurringPaymentSerializer):
    payments = serializers.SerializerMethodField()

    class Meta(RecurringPaymentSerializer.Meta):
        fields = list(RecurringPaymentSerializer.Meta.fields) + ["payments"]
        read_only_fields = fields

    def get_payments(self, obj):
        payments = getattr(obj, "prefetched_generated_expenses", None)
        if payments is None:
            payments = obj.generated_expenses.select_related(
                "month",
                "category",
                "planned_expense",
                "recurring_payment",
            ).order_by("-date", "-created_at")
        return ExpenseSerializer(payments, many=True, context=self.context).data
