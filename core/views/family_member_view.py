from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from core.models import Profile
from core.serializers.family_member_serializer import FamilyMemberSerializer


class FamilyMemberListView(ListAPIView):
    serializer_class = FamilyMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)
        return (
            User.objects.filter(profile__family=profile.family, is_active=True)
            .select_related("profile")
            .order_by("first_name", "last_name", "username")
        )
