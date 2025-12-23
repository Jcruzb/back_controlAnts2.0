from rest_framework.routers import DefaultRouter
from core.views.expense_viewset import ExpenseViewSet

router = DefaultRouter()
router.register(r'expenses', ExpenseViewSet, basename='expense')

urlpatterns = router.urls