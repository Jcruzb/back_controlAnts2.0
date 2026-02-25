from rest_framework import serializers
from core.models import IncomePlan
from core.serializers.category_serializer import CategorySerializer


class IncomePlanSerializer(serializers.ModelSerializer):
    # Read-only category detail for frontend convenience
    category_detail = CategorySerializer(source="category", read_only=True)

    class Meta:
        model = IncomePlan
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")
