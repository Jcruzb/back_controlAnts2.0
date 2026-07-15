from types import MappingProxyType

from core.assistant.errors import UnsupportedIntentError


INTENT_REGISTRY = MappingProxyType({
    "monthly_summary": {"detail": False},
    "monthly_summary_detail": {"detail": True},
    "monthly_spending": {"detail": False},
    "monthly_expenses_detail": {"detail": True},
    "monthly_cash_balance": {"detail": False},
    "pending_payments": {"detail": False},
    "pending_payments_detail": {"detail": True},
    "category_spending": {"detail": False},
    "category_spending_detail": {"detail": True},
    "payer_spending": {"detail": False},
    "payer_spending_detail": {"detail": True},
    "other_alerts_detail": {"detail": True},
})


def validate_intent(intent):
    if intent not in INTENT_REGISTRY:
        raise UnsupportedIntentError(details={"intent": intent})
    return intent
