from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views.expense_viewset import ExpenseViewSet
from core.views.recurring_generation_api import GenerateRecurringExpensesAPIView

router = DefaultRouter()
router.register(r'expenses', ExpenseViewSet, basename='expense')

urlpatterns = [
    path(
        'recurring/generate/',
        GenerateRecurringExpensesAPIView.as_view(),
        name='generate-recurring-expenses',
    ),
]

urlpatterns += router.urls