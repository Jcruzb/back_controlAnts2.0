from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from typing import Optional

from core.models import IncomePlanVersion, Month, Profile
from core.serializers.planned_income_serializer import IncomePlanVersionSerializer


def _month_key(m: Month):
    return (m.year, m.month)


def _range_overlaps(a_start, a_end, b_start, b_end):
    """Inclusive overlap for month ranges. None end means infinity."""
    inf = (9999, 12)
    a0 = _month_key(a_start)
    a1 = _month_key(a_end) if a_end is not None else inf
    b0 = _month_key(b_start)
    b1 = _month_key(b_end) if b_end is not None else inf
    return not (a1 < b0 or b1 < a0)


def _has_closed_months(family, start: Month, end: Optional[Month]) -> bool:
    """Return True if there is any closed Month within [start, end] (end can be None => infinity)."""
    qs = Month.objects.filter(family=family, is_closed=True)

    ge_start = Q(year__gt=start.year) | (Q(year=start.year) & Q(month__gte=start.month))
    qs = qs.filter(ge_start)

    if end is not None:
        le_end = Q(year__lt=end.year) | (Q(year=end.year) & Q(month__lte=end.month))
        qs = qs.filter(le_end)

    return qs.exists()


class IncomePlanVersionViewSet(ModelViewSet):
    """CRUD for IncomePlanVersion (planned amount versions per month range)."""

    serializer_class = IncomePlanVersionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)
        return IncomePlanVersion.objects.filter(
            plan__family=profile.family
        ).select_related('plan', 'valid_from', 'valid_to').order_by('valid_from__year', 'valid_from__month', 'created_at')

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)

        plan = serializer.validated_data.get('plan')
        if plan is None:
            raise ValidationError({'plan': 'Plan is required'})
        if plan.family_id != profile.family_id:
            raise ValidationError({'plan': 'Plan does not belong to your family'})

        valid_from = serializer.validated_data.get('valid_from')
        if valid_from is None:
            raise ValidationError({'valid_from': 'valid_from is required'})
        if valid_from.family_id != profile.family_id:
            raise ValidationError({'valid_from': 'valid_from does not belong to your family'})

        valid_to = serializer.validated_data.get('valid_to')
        if valid_to is not None:
            if valid_to.family_id != profile.family_id:
                raise ValidationError({'valid_to': 'valid_to does not belong to your family'})
            if _month_key(valid_to) < _month_key(valid_from):
                raise ValidationError({'valid_to': 'valid_to cannot be before valid_from'})

        planned_amount = serializer.validated_data.get('planned_amount')
        if planned_amount is None or planned_amount <= 0:
            raise ValidationError({'planned_amount': 'planned_amount must be greater than 0'})

        # Do not allow creating versions that affect closed months
        if valid_from.is_closed or (valid_to is not None and valid_to.is_closed) or _has_closed_months(profile.family, valid_from, valid_to):
            raise ValidationError({'detail': 'This month is closed and cannot be modified'})

        # Prevent overlapping versions for the same plan
        existing_versions = IncomePlanVersion.objects.filter(plan=plan)
        for v in existing_versions:
            if _range_overlaps(v.valid_from, v.valid_to, valid_from, valid_to):
                raise ValidationError({'detail': 'This version overlaps an existing version for the same plan'})

        serializer.save()

    def perform_update(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)
        instance = self.get_object()

        # Block editing if plan doesn't belong to family (safety)
        if instance.plan.family_id != profile.family_id:
            raise ValidationError({'detail': 'Not allowed'})

        plan = serializer.validated_data.get('plan', instance.plan)
        if plan.family_id != profile.family_id:
            raise ValidationError({'plan': 'Plan does not belong to your family'})

        valid_from = serializer.validated_data.get('valid_from', instance.valid_from)
        valid_to = serializer.validated_data.get('valid_to', instance.valid_to)

        if valid_from.family_id != profile.family_id:
            raise ValidationError({'valid_from': 'valid_from does not belong to your family'})
        if valid_to is not None:
            if valid_to.family_id != profile.family_id:
                raise ValidationError({'valid_to': 'valid_to does not belong to your family'})
            if _month_key(valid_to) < _month_key(valid_from):
                raise ValidationError({'valid_to': 'valid_to cannot be before valid_from'})

        planned_amount = serializer.validated_data.get('planned_amount', instance.planned_amount)
        if planned_amount is None or planned_amount <= 0:
            raise ValidationError({'planned_amount': 'planned_amount must be greater than 0'})

        # Do not allow updating versions that affect closed months
        if valid_from.is_closed or (valid_to is not None and valid_to.is_closed) or _has_closed_months(profile.family, valid_from, valid_to):
            raise ValidationError({'detail': 'This month is closed and cannot be modified'})

        # Prevent overlapping versions for the same plan (excluding itself)
        existing_versions = IncomePlanVersion.objects.filter(plan=plan).exclude(id=instance.id)
        for v in existing_versions:
            if _range_overlaps(v.valid_from, v.valid_to, valid_from, valid_to):
                raise ValidationError({'detail': 'This version overlaps an existing version for the same plan'})

        serializer.save()

    def perform_destroy(self, instance):
        profile = get_object_or_404(Profile, user=self.request.user)

        if instance.plan.family_id != profile.family_id:
            raise ValidationError({'detail': 'Not allowed'})

        if instance.valid_from.is_closed or (instance.valid_to is not None and instance.valid_to.is_closed) or _has_closed_months(profile.family, instance.valid_from, instance.valid_to):
            raise ValidationError({'detail': 'This month is closed and cannot be modified'})

        instance.delete()
