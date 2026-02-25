from django.urls import path
from rest_framework.routers import DefaultRouter

from core.views.expense_viewset import ExpenseViewSet
from core.views.income_viewset import IncomeViewSet
from core.views.recurring_generation_api import GenerateRecurringExpensesAPIView
from core.views.category_viewset import CategoryViewSet
from core.views.RecurringPayment_viewset import RecurringPaymentViewSet
from core.views.plannedExpense_viewset import PlannedExpenseViewSet
from core.views.planned_expense_plan_viewset import PlannedExpensePlanViewSet
from core.views.csrf_view import csrf
from core.views.budget_view import BudgetView

from core.views.planned_income_plan_viewset import IncomePlanViewSet
from core.views.plannedIncome_viewset import IncomePlanVersionViewSet

router = DefaultRouter()
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'recurring-payments', RecurringPaymentViewSet, basename='recurringpayment')
router.register(r'planned-expenses', PlannedExpenseViewSet, basename='plannedexpense')

router.register(
    r'planned-expense-plans',
    PlannedExpensePlanViewSet,
    basename='plannedexpenseplan'
)

router.register(
    r'income-plans',
    IncomePlanViewSet,
    basename='incomeplan'
)

router.register(
    r'income-plan-versions',
    IncomePlanVersionViewSet,
    basename='incomeplanversion'
)

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
    path("budget/", BudgetView.as_view(), name="budget"),
]

urlpatterns += router.urls