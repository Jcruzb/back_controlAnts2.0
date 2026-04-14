from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Family, Profile
from core.serializers.auth_serializer import LoginSerializer, RegisterSerializer


def _ensure_profile(user: User):
    profile = Profile.objects.select_related("family").filter(user=user).first()
    if profile is not None:
        return profile

    family = Family.objects.create(name=f"Familia de {user.username}")

    profile = Profile.objects.create(
        user=user,
        family=family,
        role="member",
    )
    return profile


def _auth_payload(user: User):
    profile = _ensure_profile(user)
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
        "profile": {
            "role": profile.role,
        },
        "family": {
            "id": profile.family_id,
            "name": profile.family.name,
        },
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        email = serializer.validated_data.get("email", "")
        family_name = serializer.validated_data.get("family_name", "").strip()

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        profile = _ensure_profile(user)
        family = profile.family
        family.name = family_name or f"Familia de {username}"
        family.save(update_fields=["name"])

        profile.role = "admin"
        profile.save(update_fields=["role"])

        login(request, user)
        return Response(_auth_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)
        return Response(_auth_payload(user), status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(
            {"authenticated": False, "detail": "Logged out"},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_auth_payload(request.user), status=status.HTTP_200_OK)
