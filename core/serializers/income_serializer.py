from rest_framework import serializers
from core.models import Income
from core.serializers.category_serializer import CategorySerializer


class IncomeSerializer(serializers.ModelSerializer):
    # Read-only nested category info to avoid extra calls on the frontend
    category_detail = CategorySerializer(source='category', read_only=True)

    class Meta:
        model = Income
        fields = '__all__'
        read_only_fields = ('user', 'month')