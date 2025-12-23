from rest_framework import serializers
from core.models import RecurringPayment


class RecurringPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecurringPayment
        fields = '__all__'
        read_only_fields = ('user',)