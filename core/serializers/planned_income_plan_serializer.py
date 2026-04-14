from django.shortcuts import get_object_or_404
from rest_framework import serializers

from core.models import Category, IncomePlan, Month, Profile
from core.serializers.category_serializer import CategorySerializer


class IncomePlanSerializer(serializers.ModelSerializer):
    # Read-only category detail for frontend convenience
    category_detail = CategorySerializer(source="category", read_only=True)
    family = serializers.PrimaryKeyRelatedField(read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.none())
    planned_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        write_only=True,
        required=False,
    )
    start_month = serializers.PrimaryKeyRelatedField(queryset=Month.objects.none())
    end_month = serializers.PrimaryKeyRelatedField(
        queryset=Month.objects.none(),
        required=False,
        allow_null=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            profile = get_object_or_404(Profile, user=request.user)
            self.fields["category"].queryset = Category.objects.filter(family=profile.family)
            month_qs = Month.objects.filter(family=profile.family)
            self.fields["start_month"].queryset = month_qs
            self.fields["end_month"].queryset = month_qs

    class Meta:
        model = IncomePlan
        fields = "__all__"
        read_only_fields = ("family", "created_by", "created_at")
