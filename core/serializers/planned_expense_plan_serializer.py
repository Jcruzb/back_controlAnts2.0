from rest_framework import serializers
from core.models import (
    PlannedExpensePlan,
    PlannedExpenseVersion,
    Month,
)
from django.utils import timezone


class PlannedExpenseVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlannedExpenseVersion
        fields = [
            "id",
            "planned_amount",
            "valid_from",
            "valid_to",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class PlannedExpensePlanSerializer(serializers.ModelSerializer):
    versions = PlannedExpenseVersionSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    # Input-only fields for creation
    planned_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        write_only=True,
        required=True,
    )
    start_month = serializers.PrimaryKeyRelatedField(
        queryset=Month.objects.all(),
        write_only=True,
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and hasattr(request.user, "family"):
            self.fields["start_month"].queryset = Month.objects.filter(
                family=request.user.family
            )

    class Meta:
        model = PlannedExpensePlan
        fields = [
            "id",
            "family",
            "category",
            "category_name",
            "name",
            "plan_type",
            "active",
            "start_month",
            "end_month",
            "planned_amount",
            "versions",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "family",
            "created_by",
            "created_at",
            "versions",
        ]

    def validate(self, attrs):
        """
        Business rules:
        - ONE_MONTH: end_month must equal start_month
        - ONGOING: end_month must be null or >= start_month
        - start_month must not be in the past
        """
        plan_type = attrs.get("plan_type")
        start_month = attrs.get("start_month")
        end_month = attrs.get("end_month")

        request = self.context.get("request")
        user = request.user if request else None

        # Security / multi-tenant: months must belong to the user's family
        if user and hasattr(user, "family"):
            if start_month and start_month.family_id != user.family_id:
                raise serializers.ValidationError("start_month is not valid for this family")
            if end_month and end_month.family_id != user.family_id:
                raise serializers.ValidationError("end_month is not valid for this family")

        # Business rule: cannot plan for past months (only current or future)
        now = timezone.now()
        if start_month:
            if (start_month.year, start_month.month) < (now.year, now.month):
                raise serializers.ValidationError("start_month cannot be in the past")

        if plan_type == "ONE_MONTH":
            attrs["end_month"] = start_month

        if plan_type == "ONGOING" and end_month and end_month < start_month:
            raise serializers.ValidationError(
                "end_month must be greater than or equal to start_month"
            )

        return attrs

    def create(self, validated_data):
        """
        Create plan + initial version atomically.
        """
        planned_amount = validated_data.pop("planned_amount")
        start_month = validated_data.get("start_month")

        request = self.context.get("request")
        user = request.user if request else None

        plan = PlannedExpensePlan.objects.create(
            **validated_data,
            family=user.family,
            created_by=user,
        )

        PlannedExpenseVersion.objects.create(
            plan=plan,
            planned_amount=planned_amount,
            valid_from=start_month,
        )

        return plan