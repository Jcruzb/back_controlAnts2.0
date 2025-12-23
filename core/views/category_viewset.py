from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.models import Category, Profile
from core.serializers.category_serializer import CategorySerializer


class CategoryViewSet(ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)
        return Category.objects.filter(family=profile.family)

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)
        serializer.save(family=profile.family)