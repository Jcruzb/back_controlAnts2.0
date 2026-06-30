from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from core.models import Expense, Category, PlannedExpense, Profile, RecurringPayment
from core.serializers.family_member_serializer import FamilyMemberSerializer
from core.services.recurring_payment_service import get_recurring_payment_month_state


class ExpenseSerializer(serializers.ModelSerializer):
    recurring_payment_month = serializers.SerializerMethodField()
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none())
    payer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.none(),
        required=False,
        allow_null=True,
    )
    payer_detail = FamilyMemberSerializer(source="payer", read_only=True)
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
            self.fields["payer"].queryset = User.objects.filter(
                profile__family=profile.family,
                is_active=True,
            )
            self.fields["planned_expense"].queryset = PlannedExpense.objects.filter(family=profile.family)
            self.fields["recurring_payment"].queryset = RecurringPayment.objects.filter(family=profile.family)

    class Meta:
        model = Expense
        fields = [
            "id",
            "description",
            "amount",
            "category",
            "payer",
            "payer_detail",
            "date",
            "month",
            "planned_expense",
            "recurring_payment",
            "recurring_payment_month",
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

    def get_recurring_payment_month(self, obj):
        if obj.recurring_payment_id is None:
            return None

        cache = getattr(self, "_recurring_payment_month_cache", None)
        if cache is None:
            cache = {}
            self._recurring_payment_month_cache = cache

        key = (obj.recurring_payment_id, obj.month_id)
        if key not in cache:
            occurrence, amounts = get_recurring_payment_month_state(
                recurring_payment=obj.recurring_payment,
                month=obj.month,
            )
            cache[key] = {
                "id": occurrence.id,
                "recurring_payment": obj.recurring_payment_id,
                "month": obj.month_id,
                "year": obj.month.year,
                "month_number": obj.month.month,
                "planned_amount": amounts.planned_amount,
                "paid_amount": amounts.paid_amount,
                "pending_amount": amounts.pending_amount,
                "difference_amount": amounts.difference_amount,
                "is_completed": amounts.is_completed,
                "status": amounts.payment_status,
                "payment_status": amounts.payment_status,
            }

        return cache[key]
