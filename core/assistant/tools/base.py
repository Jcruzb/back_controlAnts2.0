from dataclasses import asdict, dataclass
import logging
from time import monotonic
from typing import Any, Dict, Optional, Tuple

from django.core.exceptions import ObjectDoesNotExist

from core.assistant.errors import (
    AssistantError,
    AssistantPermissionDeniedError,
    InvalidArgumentsError,
)


logger = logging.getLogger("core.assistant.tools")
FORBIDDEN_TENANT_ARGUMENTS = {"user_id", "family_id", "owner_id"}


@dataclass(frozen=True)
class ToolMetadata:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_type: str
    permission: str = "authenticated_family_member"
    mode: str = "read"
    requires_confirmation: bool = False
    version: str = "1.0"

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def success(cls, data):
        return cls(ok=True, data=data)

    @classmethod
    def failure(cls, error: AssistantError):
        return cls(ok=False, error=error.to_dict())

    def to_dict(self):
        if self.ok:
            return {"ok": True, "data": self.data}
        return {"ok": False, "error": self.error}


class BaseReadTool:
    metadata: ToolMetadata
    allowed_arguments: Tuple[str, ...] = ()

    def execute(self, *, actor, family, arguments: Dict[str, Any]) -> ToolResult:
        started_at = monotonic()
        try:
            self._validate_context(actor=actor, family=family)
            self._validate_argument_names(arguments)
            data = self._execute(actor=actor, family=family, arguments=arguments)
            logger.info(
                "assistant_tool_completed",
                extra={
                    "tool_name": self.metadata.name,
                    "tool_status": "success",
                    "duration_ms": round((monotonic() - started_at) * 1000),
                },
            )
            return ToolResult.success(data)
        except AssistantError as error:
            logger.warning(
                "assistant_tool_failed",
                extra={
                    "tool_name": self.metadata.name,
                    "tool_status": "error",
                    "duration_ms": round((monotonic() - started_at) * 1000),
                    "error_code": error.code,
                },
            )
            return ToolResult.failure(error)
        except Exception:
            logger.error(
                "assistant_tool_failed",
                extra={
                    "tool_name": self.metadata.name,
                    "tool_status": "error",
                    "duration_ms": round((monotonic() - started_at) * 1000),
                    "error_code": "tool_execution_failed",
                },
            )
            return ToolResult.failure(AssistantError())

    def _validate_context(self, *, actor, family):
        if actor is None or not getattr(actor, "is_authenticated", False):
            raise AssistantPermissionDeniedError()
        try:
            profile = actor.profile
        except ObjectDoesNotExist:
            profile = None
        if profile is None or profile.family_id != family.id:
            raise AssistantPermissionDeniedError()

    def _validate_argument_names(self, arguments):
        if not isinstance(arguments, dict):
            raise InvalidArgumentsError("Los argumentos deben ser un objeto.")
        forbidden = FORBIDDEN_TENANT_ARGUMENTS.intersection(arguments)
        if forbidden:
            field = sorted(forbidden)[0]
            raise InvalidArgumentsError(
                "La identidad se obtiene de la sesión autenticada.",
                details={"field": field},
            )
        unknown = set(arguments).difference(self.allowed_arguments)
        if unknown:
            field = sorted(unknown)[0]
            raise InvalidArgumentsError(
                "El argumento no está permitido.",
                details={"field": field},
            )

    def _execute(self, *, actor, family, arguments):
        raise NotImplementedError


def validate_period(arguments):
    year = arguments.get("year")
    month = arguments.get("month")
    if isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999:
        raise InvalidArgumentsError(
            "El año debe estar entre 1 y 9999.",
            details={"field": "year"},
        )
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise InvalidArgumentsError(
            "El mes debe estar entre 1 y 12.",
            details={"field": "month"},
        )
    return year, month


def validate_limit(value, *, default, maximum):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise InvalidArgumentsError(
            f"El límite debe estar entre 1 y {maximum}.",
            details={"field": "limit"},
        )
    return value
