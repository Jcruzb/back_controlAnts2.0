from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models import Income, IncomePlan, Month, Profile
from core.serializers.income_serializer import IncomeSerializer


class IncomeViewSet(ModelViewSet):
    serializer_class = IncomeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        profile = get_object_or_404(Profile, user=self.request.user)

        queryset = Income.objects.filter(
            month__family=profile.family
        ).select_related('category', 'income_plan').order_by('-date', '-created_at')

        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')

        if year and month:
            try:
                year_int = int(year)
                month_int = int(month)
            except (TypeError, ValueError):
                raise ValidationError({'detail': 'Query params year and month must be integers'})

            queryset = queryset.filter(
                month__year=year_int,
                month__month=month_int
            )

        return queryset

    def _validate_category_and_plan(self, profile, serializer, month_obj=None):
        """Validate category ownership and optional income_plan consistency."""
        category = serializer.validated_data.get('category')
        if category is None:
            raise ValidationError({'category': 'Category is required'})
        if category.family_id != profile.family_id:
            raise ValidationError({'category': 'Category does not belong to your family'})

        income_plan = serializer.validated_data.get('income_plan')
        if income_plan is not None:
            # Safety: ensure plan belongs to the same family
            if income_plan.family_id != profile.family_id:
                raise ValidationError({'income_plan': 'Income plan does not belong to your family'})

            # Consistency: incomes generated from a plan must keep the plan's category
            if category.id != income_plan.category_id:
                raise ValidationError({'category': 'Category must match the income plan category'})

            # Optional pre-check for duplicates (DB constraint is the real guard)
            if month_obj is not None:
                if Income.objects.filter(month=month_obj, income_plan=income_plan).exists():
                    raise ValidationError({'income_plan': 'This income plan is already resolved for this month'})

    def perform_create(self, serializer):
        profile = get_object_or_404(Profile, user=self.request.user)

        income_date = serializer.validated_data.get('date')
        if not income_date:
            raise ValidationError({'date': 'Date is required'})

        month_obj, _ = Month.objects.get_or_create(
            family=profile.family,
            year=income_date.year,
            month=income_date.month,
            defaults={'is_closed': False},
        )

        if month_obj.is_closed:
            raise ValidationError('This month is closed and cannot be modified')

        amount = serializer.validated_data.get('amount')
        if amount is None or amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than 0'})

        self._validate_category_and_plan(profile, serializer, month_obj=month_obj)

        try:
            serializer.save(
                user=self.request.user,
                month=month_obj,
            )
        except IntegrityError:
            # Most likely: uniq_income_per_month_per_income_plan
            raise ValidationError({'income_plan': 'This income plan is already resolved for this month'})

    def perform_update(self, serializer):
        instance = self.get_object()

        profile = get_object_or_404(Profile, user=self.request.user)

        # Block modifications if the current month is closed
        if instance.month.is_closed:
            raise ValidationError('This month is closed and cannot be modified')

        # Validate amount if provided
        amount = serializer.validated_data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationError({'amount': 'Amount must be greater than 0'})

        # Validate plan ownership if provided (and keep category consistent when plan is set)
        # Determine target month (existing or new, if date changes)
        new_date = serializer.validated_data.get('date')
        target_month = instance.month
        if new_date is not None:
            month_obj, _ = Month.objects.get_or_create(
                family=profile.family,
                year=new_date.year,
                month=new_date.month,
                defaults={'is_closed': False},
            )
            if month_obj.is_closed:
                raise ValidationError('This month is closed and cannot be modified')
            target_month = month_obj

        # Category validation: if not provided, use instance.category
        if 'category' not in serializer.validated_data:
            serializer.validated_data['category'] = instance.category

        # Plan validation: if not provided, use instance.income_plan
        if 'income_plan' not in serializer.validated_data:
            serializer.validated_data['income_plan'] = instance.income_plan

        # If plan is being changed, validate it belongs to family
        income_plan = serializer.validated_data.get('income_plan')
        if income_plan is not None:
            # Ensure we have a real IncomePlan instance
            if isinstance(income_plan, int):
                income_plan = get_object_or_404(IncomePlan, id=income_plan)
                serializer.validated_data['income_plan'] = income_plan

        # Validate category/plan consistency and duplicate guarding (exclude current instance)
        self._validate_category_and_plan(profile, serializer)
        if serializer.validated_data.get('income_plan') is not None:
            exists = Income.objects.filter(
                month=target_month,
                income_plan=serializer.validated_data['income_plan'],
            ).exclude(id=instance.id).exists()
            if exists:
                raise ValidationError({'income_plan': 'This income plan is already resolved for this month'})

        try:
            if new_date is not None:
                serializer.save(month=target_month)
                return

            serializer.save()
        except IntegrityError:
            raise ValidationError({'income_plan': 'This income plan is already resolved for this month'})

    def perform_destroy(self, instance):
        # Block deletes for closed months
        if instance.month.is_closed:
            raise ValidationError('This month is closed and cannot be modified')

        instance.delete()