from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views.expense_viewset import ExpenseViewSet
from core.views.income_viewset import IncomeViewSet
from core.views.recurring_generation_api import GenerateRecurringExpensesAPIView
from core.views.category_viewset import CategoryViewSet
from core.views.RecurringPayment_viewset import RecurringPaymentViewSet
from core.views.csrf_view import csrf

router = DefaultRouter()
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'recurring-payments', RecurringPaymentViewSet, basename='recurringpayment')

urlpatterns = [
    path(
        'recurring/generate/',
        GenerateRecurringExpensesAPIView.as_view(),
        name='generate-recurring-expenses',
    ),
    path(
        'incomes/',
        IncomeViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='income-list-create',
    ),
    
    path('csrf/', csrf, name='csrf'),
]

urlpatterns += router.urls