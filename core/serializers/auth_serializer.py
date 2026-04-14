from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True)
    family_name = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError("username is required")
        if User.objects.filter(username__iexact=username).exists():
            raise serializers.ValidationError("username already exists")
        return username

    def validate_email(self, value):
        email = value.strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("email already exists")
        return email

    def validate_password(self, value):
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
