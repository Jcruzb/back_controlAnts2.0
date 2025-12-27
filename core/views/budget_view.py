from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from core.services.budget_service import BudgetService


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
        return Response(data)
