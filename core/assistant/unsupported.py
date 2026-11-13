from dataclasses import asdict, dataclass
import logging
from typing import Optional


logger = logging.getLogger("core.assistant.unsupported")


SUPPORTED_CATEGORIES = {
    "unsupported_intent",
    "missing_endpoint",
    "insufficient_data",
    "invalid_arguments",
    "permission_denied",
    "technical_error",
    "out_of_domain",
}


@dataclass(frozen=True)
class UnsupportedRequestRecord:
    category: str
    provider: str
    tool_name: Optional[str]
    error_code: str
    request_id: str

    def to_dict(self):
        return asdict(self)


class UnsupportedRequestClassifier:
    ERROR_CATEGORY_MAP = {
        "ai_consent_required": "unsupported_intent",
        "unsupported_request": "unsupported_intent",
        "unsupported_tool": "missing_endpoint",
        "resource_not_found": "insufficient_data",
        "invalid_arguments": "invalid_arguments",
        "permission_denied": "permission_denied",
        "tool_execution_failed": "technical_error",
        "provider_unavailable": "technical_error",
        "unsupported_intent": "unsupported_intent",
        "ambiguous_period": "invalid_arguments",
        "invalid_period": "invalid_arguments",
        "invalid_action": "invalid_arguments",
        "invalid_visual_block": "technical_error",
        "unsupported_block_type": "technical_error",
        "invalid_table": "technical_error",
        "invalid_chart": "technical_error",
    }

    def classify(self, *, error_code, provider, request_id, tool_name=None):
        category = self.ERROR_CATEGORY_MAP.get(error_code, "out_of_domain")
        record = UnsupportedRequestRecord(
            category=category,
            provider=provider,
            tool_name=tool_name,
            error_code=error_code,
            request_id=request_id,
        )
        logger.info("assistant_request_unmet", extra=record.to_dict())
        return record
