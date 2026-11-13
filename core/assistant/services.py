import hashlib
import hmac
import logging
from datetime import date
from time import monotonic
import uuid

from django.conf import settings

from core.assistant.errors import (
    AssistantError,
    AIConsentRequiredError,
    ProviderUnavailableError,
    UnsupportedToolError,
)
from core.assistant.deterministic import DeterministicAssistantService
from core.assistant.deterministic.normalizer import current_local_date
from core.assistant.providers import MockAssistantProvider, OpenAIAssistantProvider
from core.assistant.registry import ToolRegistry
from core.assistant.tools.base import validate_period
from core.assistant.unsupported import UnsupportedRequestClassifier


logger = logging.getLogger("core.assistant")

TOOL_TO_INTENT = {
    "get_monthly_budget": "monthly_summary",
    "get_monthly_cash_summary": "monthly_cash_balance",
    "list_monthly_expenses": "monthly_spending",
    "get_recurring_payment_status": "pending_payments",
    "get_category_spending": "category_spending",
    "get_payer_spending": "payer_spending",
}


def pseudonymize_identifier(value):
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        str(value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:16]


class AssistantApplicationService:
    def __init__(
        self,
        *,
        registry=None,
        provider=None,
        classifier=None,
        deterministic_service=None,
    ):
        self.registry = registry or ToolRegistry()
        self._provider = provider
        self.classifier = classifier or UnsupportedRequestClassifier()
        self.deterministic_service = deterministic_service or DeterministicAssistantService()

    @property
    def provider(self):
        if self._provider is None:
            self._provider = self._build_provider()
        return self._provider

    def _build_provider(self):
        if settings.ASSISTANT_PROVIDER == "mock":
            return MockAssistantProvider()
        if settings.ASSISTANT_PROVIDER == "openai":
            return OpenAIAssistantProvider()
        raise ProviderUnavailableError()

    def process(self, *, actor, family, message, context=None, allow_ai=False):
        request_id = f"req_{uuid.uuid4()}"
        started_at = monotonic()
        tool_name = None
        try:
            reference_date = self._reference_date(context)
            match = self.deterministic_service.can_handle(
                message=message,
                reference_date=reference_date,
            )
            if match.can_respond:
                response = self.deterministic_service.respond(
                    intent=match.intent,
                    arguments=match.arguments,
                    actor=actor,
                    family=family,
                    request_id=request_id,
                )
                self._log_success(
                    request_id=request_id,
                    actor=actor,
                    family=family,
                    started_at=started_at,
                    provider="none",
                    tool_name=None,
                    source="deterministic",
                )
                return response

            if allow_ai is not True:
                raise AIConsentRequiredError()

            decision = self.provider.respond(
                messages=[{"role": "user", "content": message}],
                available_tools=self.registry.metadata(),
                context={
                    "request_id": request_id,
                    "default_period": {
                        "year": reference_date.year,
                        "month": reference_date.month,
                    },
                },
            )
            tool_name = decision.tool_name
            self.registry.get(tool_name)
            intent = TOOL_TO_INTENT.get(tool_name)
            if intent is None:
                raise UnsupportedToolError()
            year, month = validate_period({
                "year": decision.arguments.get("year"),
                "month": decision.arguments.get("month"),
            })
            response = self.deterministic_service.respond(
                intent=intent,
                arguments={
                    "year": year,
                    "month": month,
                },
                actor=actor,
                family=family,
                request_id=request_id,
            )
            response["source"] = "hybrid"
            response["meta"]["provider"] = self.provider.name
            response["meta"]["model"] = getattr(self.provider, "model", None)
            response["meta"]["tool_call"] = {
                "name": tool_name,
                "status": "success",
            }
            self._log_success(
                request_id=request_id,
                actor=actor,
                family=family,
                started_at=started_at,
                provider=self.provider.name,
                tool_name=tool_name,
                source="provider",
            )
            return response
        except AssistantError as error:
            self.classifier.classify(
                error_code=error.code,
                provider=self._provider_name(),
                request_id=request_id,
                tool_name=tool_name,
            )
            logger.warning(
                "assistant_request_failed",
                extra={
                    "request_id": request_id,
                    "actor_ref": pseudonymize_identifier(actor.id),
                    "family_ref": pseudonymize_identifier(family.id),
                    "provider": self._provider_name(),
                    "tool_name": tool_name,
                    "tool_status": "error",
                    "duration_ms": round((monotonic() - started_at) * 1000),
                    "error_code": error.code,
                },
            )
            raise

    @staticmethod
    def _reference_date(context):
        if context:
            return date(context["year"], context["month"], 1)
        return current_local_date()

    def process_intent(self, *, actor, family, intent, arguments):
        request_id = f"req_{uuid.uuid4()}"
        started_at = monotonic()
        try:
            response = self.deterministic_service.respond(
                intent=intent,
                arguments=arguments,
                actor=actor,
                family=family,
                request_id=request_id,
            )
            self._log_success(
                request_id=request_id,
                actor=actor,
                family=family,
                started_at=started_at,
                provider="none",
                tool_name=None,
                source="deterministic",
            )
            return response
        except AssistantError as error:
            self.classifier.classify(
                error_code=error.code,
                provider="none",
                request_id=request_id,
                tool_name=None,
            )
            logger.warning(
                "assistant_request_failed",
                extra={
                    "request_id": request_id,
                    "actor_ref": pseudonymize_identifier(actor.id),
                    "family_ref": pseudonymize_identifier(family.id),
                    "provider": "none",
                    "source": "deterministic",
                    "tool_name": None,
                    "tool_status": "error",
                    "duration_ms": round((monotonic() - started_at) * 1000),
                    "error_code": error.code,
                },
            )
            raise

    def _provider_name(self):
        return getattr(self._provider, "name", settings.ASSISTANT_PROVIDER)

    @staticmethod
    def _log_success(*, request_id, actor, family, started_at, provider, tool_name, source):
        logger.info(
            "assistant_request_completed",
            extra={
                "request_id": request_id,
                "actor_ref": pseudonymize_identifier(actor.id),
                "family_ref": pseudonymize_identifier(family.id),
                "provider": provider,
                "source": source,
                "tool_name": tool_name,
                "tool_status": "success",
                "duration_ms": round((monotonic() - started_at) * 1000),
            },
        )
