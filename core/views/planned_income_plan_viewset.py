from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import calendar
import datetime
from typing import Optional

from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import Income, IncomePlan, IncomePlanVersion, Month, Profile
from core.serializers.category_serializer import CategorySerializer
from core.serializers.planned_income_plan_serializer import IncomePlanSerializer


def _month_key(m: Month):
    return (m.year, m.month)


def _lte_month_q(prefix: str, year: int, month: int) -> Q:
    return Q(**{f"{prefix}__year__lt": year}) | (
        Q(**{f"{prefix}__year": year}) & Q(**{f"{prefix}__month__lte": month})
    )


def _gte_month_q(prefix: str, year: int, month: int) -> Q:
    return Q(**{f"{prefix}__year__gt": year}) | (
        Q(**{f"{prefix}__year": year}) & Q(**{f"{prefix}__month__gte": month})
    )


def _get_version_for_month(plan: IncomePlan, year: int, month: int):
    return (
        IncomePlanVersion.objects.filter(plan=plan)
        .filter(_lte_month_q('valid_from', year, month))
        .filter(Q(valid_to__isnull=True) | _gte_month_q('valid_to', year, month))
        .select_related('valid_from', 'valid_to')
        .order_by('valid_from__year', 'valid_from__month', 'created_at')
        .last()
    )


def _default_income_date(year: int, month: int, due_day: int = None) -> datetime.date:
    last_day = calendar.monthrange(year, month)[1]
    if due_day is None:
        day = last_day
    else:
        day = max(1, min(int(due_day), last_day))
    return datetime.date(year, month, day)


def _parse_yyyy_mm_dd(value: str) -> datetime.date:
    try:
        y, m, d = [int(x) for x in value.split('-')]
        return datetime.date(y, m, d)
    except Exception:
        raise ValidationError({'date': 'date must be in YYYY-MM-DD format'})



def _to_decimal_amount(value) -> Decimal:
    """Parse an amount as Decimal with 2 decimal places."""
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({'amount': 'amount must be a number'})

    if dec <= 0:
        raise ValidationError({'amount': 'amount must be greater than 0'})

    return dec.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# Helper to check for closed months in a range
from typing import Optional
# ...
def _has_closed_months_in_range(family, start: Month, end: Optional[Month]) -> bool:
    """True if there is any closed Month within [start, end]. If end is None, checks from start onwards."""
    qs = Month.objects.filter(family=family, is_closed=True)

    ge_start = Q(year__gt=start.year) | (Q(year=start.year) & Q(month__gte=start.month))
    qs = qs.filter(ge_start)

    if end is not None:
        le_end = Q(year__lt=end.year) | (Q(year=end.year) & Q(month__lte=end.month))
        qs = qs.filter(le_end)

    return qs.exists()


class IncomePlanViewSet(ModelViewSet):
    """CRUD for IncomePlan (salary/recurrent planned income definition)."""

    serializer_class = IncomePlanSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)
        return IncomePlan.objects.filter(
            family=profile.family
        ).select_related('category', 'start_month', 'end_month').order_by('-created_at')

    def _validate_family_consistency(self, profile, serializer):
        category = serializer.validated_data.get('category')
        if category is not None and category.family_id != profile.family_id:
            raise ValidationError({'category': 'Category does not belong to your family'})

        start_month = serializer.validated_data.get('start_month')
        if start_month is not None and start_month.family_id != profile.family_id:
            raise ValidationError({'start_month': 'Start month does not belong to your family'})

        end_month = serializer.validated_data.get('end_month')
        if end_month is not None and end_month.family_id != profile.family_id:
            raise ValidationError({'end_month': 'End month does not belong to your family'})

        # Validate month ordering if both are present
        if start_month is not None and end_month is not None:
            if _month_key(end_month) < _month_key(start_month):
                raise ValidationError({'end_month': 'End month cannot be before start month'})

        plan_type = serializer.validated_data.get('plan_type')
        if plan_type == 'ONE_MONTH' and start_month is not None:
            # For one-month plans, default end_month to start_month when omitted
            if end_month is None:
                serializer.validated_data['end_month'] = start_month

        due_day = serializer.validated_data.get('due_day')
        if due_day is not None and (due_day < 1 or due_day > 31):
            raise ValidationError({'due_day': 'due_day must be between 1 and 31'})

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)

        # Ensure required relations are consistent with family
        self._validate_family_consistency(profile, serializer)

        serializer.save(
            family=profile.family,
            created_by=self.request.user,
        )

    def perform_update(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)
        instance = self.get_object()

        self._validate_family_consistency(profile, serializer)

        # Determine the resulting range after update
        start_month = serializer.validated_data.get('start_month', instance.start_month)
        end_month = serializer.validated_data.get('end_month', instance.end_month)

        # For ONE_MONTH, align end_month to start_month (same logic as validation)
        plan_type = serializer.validated_data.get('plan_type', instance.plan_type)
        if plan_type == 'ONE_MONTH' and start_month is not None:
            end_month = start_month

        # Block edits that affect any closed month
        if start_month is not None and _has_closed_months_in_range(profile.family, start_month, end_month):
            raise ValidationError({'detail': 'This month is closed and cannot be modified'})

        # Prevent changing ownership fields from client
        serializer.save(
            family=profile.family,
        )


    def _parse_year_month(self, request):
        year = request.query_params.get('year') or request.data.get('year')
        month = request.query_params.get('month') or request.data.get('month')
        if year is None or month is None:
            raise ValidationError({'detail': 'year and month are required'})
        try:
            year_int = int(year)
            month_int = int(month)
        except (TypeError, ValueError):
            raise ValidationError({'detail': 'year and month must be integers'})
        if month_int < 1 or month_int > 12:
            raise ValidationError({'month': 'month must be between 1 and 12'})
        return year_int, month_int

    def _ensure_plan_applies(self, plan: IncomePlan, year: int, month: int):
        if (plan.start_month.year, plan.start_month.month) > (year, month):
            raise ValidationError({'detail': 'Plan does not apply to this month'})
        if plan.end_month is not None and (plan.end_month.year, plan.end_month.month) < (year, month):
            raise ValidationError({'detail': 'Plan does not apply to this month'})

    @action(detail=False, methods=['get'], url_path='month')
    def month(self, request):
        year_int, month_int = self._parse_year_month(request)
        profile = get_object_or_404(Profile, user=request.user)

        month_obj, _ = Month.objects.get_or_create(
            family=profile.family,
            year=year_int,
            month=month_int,
            defaults={'is_closed': False},
        )

        plans = (
            IncomePlan.objects.filter(family=profile.family, active=True)
            .filter(_lte_month_q('start_month', year_int, month_int))
            .filter(Q(end_month__isnull=True) | _gte_month_q('end_month', year_int, month_int))
            .select_related('category', 'start_month', 'end_month')
            .order_by('-created_at')
        )

        results = []
        for plan in plans:
            version = _get_version_for_month(plan, year_int, month_int)
            existing_income = (
                Income.objects.filter(month=month_obj, income_plan=plan)
                .select_related('category')
                .order_by('-created_at')
                .first()
            )

            if existing_income:
                status = 'RESOLVED'
            else:
                status = 'PENDING' if version is not None else 'MISSING_VERSION'

            results.append({
                'plan_id': plan.id,
                'name': plan.name,
                'plan_type': plan.plan_type,
                'due_day': plan.due_day,
                'category': plan.category_id,
                'category_detail': CategorySerializer(plan.category).data,
                'version_id': version.id if version else None,
                'planned_amount': str(version.planned_amount) if version else None,
                'status': status,
                'can_resolve': (not month_obj.is_closed) and (version is not None) and (existing_income is None),
                'resolved_income': {
                    'id': existing_income.id,
                    'amount': str(existing_income.amount),
                    'date': existing_income.date,
                    'description': existing_income.description,
                } if existing_income else None,
            })

        return Response({
            'month': {'year': year_int, 'month': month_int, 'is_closed': month_obj.is_closed},
            'results': results,
        })

    def _create_income_for_plan(self, request, plan: IncomePlan, year_int: int, month_int: int, amount, date_value=None, description=''):
        profile = get_object_or_404(Profile, user=request.user)
        if plan.family_id != profile.family_id:
            raise ValidationError({'detail': 'Not allowed'})

        plan = IncomePlan.objects.select_related('start_month', 'end_month', 'category').get(id=plan.id)
        self._ensure_plan_applies(plan, year_int, month_int)

        if not plan.active:
            raise ValidationError({'detail': 'Plan is not active'})

        month_obj, _ = Month.objects.get_or_create(
            family=profile.family,
            year=year_int,
            month=month_int,
            defaults={'is_closed': False},
        )
        if month_obj.is_closed:
            raise ValidationError({'detail': 'This month is closed and cannot be modified'})

        version = _get_version_for_month(plan, year_int, month_int)
        if version is None:
            raise ValidationError({'detail': 'No plan version found for this month'})

        amount_value = _to_decimal_amount(amount)

        if date_value is None:
            date_obj = _default_income_date(year_int, month_int, plan.due_day)
        else:
            if isinstance(date_value, str):
                date_obj = _parse_yyyy_mm_dd(date_value)
            elif isinstance(date_value, datetime.date):
                date_obj = date_value
            else:
                raise ValidationError({'date': 'Invalid date value'})

            if date_obj.year != year_int or date_obj.month != month_int:
                raise ValidationError({'date': 'date must be within the selected month'})

        try:
            income = Income.objects.create(
                month=month_obj,
                user=request.user,
                amount=amount_value,
                category=plan.category,
                income_plan=plan,
                date=date_obj,
                description=description or '',
            )
        except IntegrityError:
            raise ValidationError({'detail': 'This income plan is already resolved for this month'})

        return income

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        year_int, month_int = self._parse_year_month(request)
        plan = self.get_object()

        version = _get_version_for_month(plan, year_int, month_int)
        if version is None:
            raise ValidationError({'detail': 'No plan version found for this month'})

        income = self._create_income_for_plan(
            request,
            plan,
            year_int,
            month_int,
            amount=str(version.planned_amount),
            date_value=None,
            description=(request.data.get('description', '') if isinstance(request.data, dict) else ''),
        )

        return Response({'detail': 'OK', 'income_id': income.id})

    @action(detail=True, methods=['post'], url_path='adjust')
    def adjust(self, request, pk=None):
        year_int, month_int = self._parse_year_month(request)
        plan = self.get_object()

        amount = request.data.get('amount')
        date_value = request.data.get('date')
        description = request.data.get('description', '')

        income = self._create_income_for_plan(
            request,
            plan,
            year_int,
            month_int,
            amount=amount,
            date_value=date_value,
            description=description,
        )

        return Response({'detail': 'OK', 'income_id': income.id})

    def perform_destroy(self, instance):
        profile = get_object_or_404(Profile, user=self.request.user)

        if instance.family_id != profile.family_id:
            raise ValidationError({'detail': 'Not allowed'})

        if _has_closed_months_in_range(profile.family, instance.start_month, instance.end_month):
            raise ValidationError({'detail': 'This month is closed and cannot be modified'})

        instance.delete()