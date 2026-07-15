from typing import Dict, Optional


class AssistantError(Exception):
    code = "tool_execution_failed"
    public_message = "No se pudo completar la solicitud."
    http_status = 500

    def __init__(self, message=None, *, details: Optional[Dict] = None):
        super().__init__(message or self.public_message)
        self.message = message or self.public_message
        self.details = details or {}

    def to_dict(self):
        error = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return error


class InvalidArgumentsError(AssistantError):
    code = "invalid_arguments"
    public_message = "Los argumentos no son válidos."
    http_status = 400


class UnsupportedToolError(AssistantError):
    code = "unsupported_tool"
    public_message = "La herramienta solicitada no está disponible."
    http_status = 400


class AssistantPermissionDeniedError(AssistantError):
    code = "permission_denied"
    public_message = "No tienes permiso para consultar este recurso."
    http_status = 403


class ResourceNotFoundError(AssistantError):
    code = "resource_not_found"
    public_message = "El recurso solicitado no existe."
    http_status = 404


class AssistantDisabledError(AssistantError):
    code = "assistant_disabled"
    public_message = "El asistente no está habilitado."
    http_status = 503


class ProviderUnavailableError(AssistantError):
    code = "provider_unavailable"
    public_message = "El proveedor del asistente no está disponible."
    http_status = 503


class UnsupportedRequestError(AssistantError):
    code = "unsupported_request"
    public_message = "La solicitud no está soportada por el asistente simulado."
    http_status = 400


class InvalidVisualBlockError(AssistantError):
    code = "invalid_visual_block"
    public_message = "El bloque visual no es válido."
    http_status = 400


class UnsupportedBlockTypeError(AssistantError):
    code = "unsupported_block_type"
    public_message = "El tipo de bloque visual no está permitido."
    http_status = 400


class InvalidActionError(AssistantError):
    code = "invalid_action"
    public_message = "La acción no es válida."
    http_status = 400


class UnsupportedIntentError(AssistantError):
    code = "unsupported_intent"
    public_message = "La intención solicitada no está disponible."
    http_status = 400


class AmbiguousPeriodError(AssistantError):
    code = "ambiguous_period"
    public_message = "El periodo solicitado es ambiguo."
    http_status = 400


class InvalidPeriodError(AssistantError):
    code = "invalid_period"
    public_message = "El periodo solicitado no es válido."
    http_status = 400


class DeterministicMatchFailedError(AssistantError):
    code = "deterministic_match_failed"
    public_message = "No se pudo determinar la consulta solicitada."
    http_status = 400


class DetailNotAvailableError(AssistantError):
    code = "detail_not_available"
    public_message = "El detalle solicitado no está disponible."
    http_status = 400


class TooManyBlocksError(AssistantError):
    code = "too_many_blocks"
    public_message = "La respuesta contiene demasiados bloques."
    http_status = 400


class TooManyAlertsError(AssistantError):
    code = "too_many_alerts"
    public_message = "La respuesta contiene demasiadas alertas visibles."
    http_status = 400


class InvalidTableError(AssistantError):
    code = "invalid_table"
    public_message = "La tabla no es válida."
    http_status = 400


class InvalidChartError(AssistantError):
    code = "invalid_chart"
    public_message = "El gráfico no es válido."
    http_status = 400


ERROR_TYPES = {
    error_type.code: error_type
    for error_type in (
        InvalidArgumentsError,
        UnsupportedToolError,
        AssistantPermissionDeniedError,
        ResourceNotFoundError,
        AssistantDisabledError,
        ProviderUnavailableError,
        UnsupportedRequestError,
        InvalidVisualBlockError,
        UnsupportedBlockTypeError,
        InvalidActionError,
        UnsupportedIntentError,
        AmbiguousPeriodError,
        InvalidPeriodError,
        DeterministicMatchFailedError,
        DetailNotAvailableError,
        TooManyBlocksError,
        TooManyAlertsError,
        InvalidTableError,
        InvalidChartError,
    )
}


def error_from_payload(payload):
    error_type = ERROR_TYPES.get(payload.get("code"), AssistantError)
    return error_type(
        payload.get("message"),
        details=payload.get("details"),
    )
