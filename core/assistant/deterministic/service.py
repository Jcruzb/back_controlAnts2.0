from core.assistant.deterministic.details import DetailResponseBuilder
from core.assistant.deterministic.normalizer import resolve_period_from_arguments
from core.assistant.deterministic.responses import InitialResponseBuilder
from core.assistant.deterministic.router import DeterministicIntentRouter
from core.assistant.intents import INTENT_REGISTRY, validate_intent


class DeterministicAssistantService:
    def __init__(self, *, router=None):
        self.router = router or DeterministicIntentRouter()

    def can_handle(self, *, message, reference_date=None):
        return self.router.match(message, reference_date=reference_date)

    def respond(self, *, intent, arguments, actor, family, request_id):
        validate_intent(intent)
        period = resolve_period_from_arguments(arguments)
        builder_class = (
            DetailResponseBuilder
            if INTENT_REGISTRY[intent]["detail"]
            else InitialResponseBuilder
        )
        return builder_class(
            actor=actor,
            family=family,
            request_id=request_id,
        ).build(intent=intent, year=period.year, month=period.month)
