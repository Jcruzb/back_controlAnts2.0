from rest_framework import serializers

from django.contrib.auth.models import User


class FamilyMemberSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    role = serializers.CharField(source="profile.role", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "display_name",
            "role",
        ]

    def get_display_name(self, obj):
        full_name = obj.get_full_name().strip()
        return full_name or obj.username
