import hashlib
import hmac
import logging
from time import monotonic
import uuid

from django.conf import settings

from core.assistant.errors import (
    AssistantError,
    ProviderUnavailableError,
    error_from_payload,
)
from core.assistant.deterministic import DeterministicAssistantService
from core.assistant.providers import MockAssistantProvider
from core.assistant.registry import ToolRegistry
from core.assistant.unsupported import UnsupportedRequestClassifier


logger = logging.getLogger("core.assistant")


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
        raise ProviderUnavailableError()

    def process(self, *, actor, family, message):
        request_id = f"req_{uuid.uuid4()}"
        started_at = monotonic()
        tool_name = None
        try:
            match = self.deterministic_service.can_handle(message=message)
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

            decision = self.provider.respond(
                messages=[{"role": "user", "content": message}],
                available_tools=self.registry.metadata(),
                context={"request_id": request_id},
            )
            tool_name = decision.tool_name
            tool = self.registry.get(tool_name)
            result = tool.execute(
                actor=actor,
                family=family,
                arguments=decision.arguments,
            )
            if not result.ok:
                raise error_from_payload(result.error)

            response = {
                "message": self._format_message(tool_name=tool_name, data=result.data),
                "period": result.data.get("period"),
                "tool_calls": [{"name": tool_name, "status": "success"}],
                "data": result.data,
                "provider": self.provider.name,
                "request_id": request_id,
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

    def _format_message(self, *, tool_name, data):
        period = data.get("period") or {}
        label = period.get("label", "Periodo solicitado")
        if tool_name == "get_monthly_budget":
            planned = data["planned"]
            return (
                f"{label}: {planned['total']} {data['currency']} planificados, "
                f"{planned['paid']} pagados y {planned['pending']} pendientes."
            )
        if tool_name == "get_monthly_cash_summary":
            return (
                f"{label}: balance de caja {data['cash_balance']} {data['currency']} "
                f"con {data['income']['actual']} de ingresos reales."
            )
        return f"{label}: consulta completada con {data.get('count', 0)} resultados."
