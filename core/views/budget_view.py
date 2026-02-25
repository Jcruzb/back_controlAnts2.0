from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Income, IncomePlan, IncomePlanVersion, Month
from core.serializers.category_serializer import CategorySerializer
from core.services.budget_service import BudgetService


# Helper functions for month comparisons and income plan month status
def _lte_month_q(prefix: str, year: int, month: int) -> Q:
    """(prefix.year < year) OR (prefix.year==year AND prefix.month<=month)"""
    return Q(**{f"{prefix}__year__lt": year}) | (
        Q(**{f"{prefix}__year": year}) & Q(**{f"{prefix}__month__lte": month})
    )


def _gte_month_q(prefix: str, year: int, month: int) -> Q:
    """(prefix.year > year) OR (prefix.year==year AND prefix.month>=month)"""
    return Q(**{f"{prefix}__year__gt": year}) | (
        Q(**{f"{prefix}__year": year}) & Q(**{f"{prefix}__month__gte": month})
    )


def build_income_plan_month_status(family, year: int, month: int):
    """Return income plans applicable to (year, month) with PENDING/RESOLVED status.

    This is used by the BudgetView so the frontend can show 'planificados pendientes' and
    resolve them (confirm/adjust) later.
    """
    month_obj, _ = Month.objects.get_or_create(
        family=family,
        year=year,
        month=month,
        defaults={'is_closed': False},
    )

    plans = IncomePlan.objects.filter(
        family=family,
        active=True,
    ).filter(
        _lte_month_q('start_month', year, month)
    ).filter(
        Q(end_month__isnull=True) | _gte_month_q('end_month', year, month)
    ).select_related('category', 'start_month', 'end_month').order_by('-created_at')

    results = []
    for plan in plans:
        version = IncomePlanVersion.objects.filter(
            plan=plan,
        ).filter(
            _lte_month_q('valid_from', year, month)
        ).filter(
            Q(valid_to__isnull=True) | _gte_month_q('valid_to', year, month)
        ).select_related('valid_from', 'valid_to').order_by(
            'valid_from__year', 'valid_from__month', 'created_at'
        ).last()

        existing_income = Income.objects.filter(
            month=month_obj,
            income_plan=plan,
        ).select_related('category').order_by('-created_at').first()

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

    return {
        'month': {'year': year, 'month': month, 'is_closed': month_obj.is_closed},
        'results': results,
    }


class BudgetView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        year = request.query_params.get("year")
        month = request.query_params.get("month")

        if not year or not month:
            raise ValidationError("year and month are required")

        try:
            year = int(year)
            month = int(month)
        except ValueError:
            raise ValidationError("year and month must be integers")

        service = BudgetService(
            family=request.user.profile.family,
            year=year,
            month=month,
        )

        data = service.build_budget()

        # Income plans (salary/recurrent) status for this month
        data['income_plan_month'] = build_income_plan_month_status(
            family=request.user.profile.family,
            year=year,
            month=month,
        )

        return Response(data)
