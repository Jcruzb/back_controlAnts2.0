from rest_framework import serializers
from core.models import IncomePlanVersion


class IncomePlanVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomePlanVersion
        fields = "__all__"
        read_only_fields = ("created_at",)
